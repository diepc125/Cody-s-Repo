"""SEC Form 4 insider trade tracker.

Uses the public EDGAR submissions API — no API key required.
SEC requires a descriptive User-Agent and enforces a 10 req/s rate limit.
We stay within that via per-ticker caching (1-hour TTL).

Scoring:
  score = (buy_shares - sell_shares) / (buy_shares + sell_shares)  → [-1, +1]
  Both non-derivative (open market) and derivative (RSU/option) transactions
  are counted so tech execs show up correctly.
"""

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_EDGAR_BASE  = "https://data.sec.gov"
_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"
_TICKERS_URL  = "https://www.sec.gov/files/company_tickers.json"

_HEADERS = {
    "User-Agent": "Sentinel TradingApp sentinel-trading@proton.me",
    "Accept-Encoding": "gzip, deflate",
}

_LOOKBACK_DAYS = 90
_MAX_FILINGS   = 3
_CACHE_TTL     = 3600


# ── CIK map ───────────────────────────────────────────────────────────────────

_cik_map: dict[str, str] = {}


def _load_cik_map() -> None:
    """Populate the in-memory ticker→CIK map from EDGAR's bulk JSON (once)."""
    if _cik_map:
        return
    try:
        resp = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        for entry in resp.json().values():
            _cik_map[entry["ticker"].upper()] = str(entry["cik_str"]).zfill(10)
        logger.info("sec_insider: loaded %d CIK mappings", len(_cik_map))
    except Exception as exc:
        logger.warning("sec_insider: CIK map load failed: %s", exc)


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class InsiderTransaction:
    name: str
    title: str
    transaction_type: str   # "Buy" | "Sell" | "Other"
    shares: float
    price: float | None
    value: float | None
    date: str
    days_ago: int


@dataclass
class InsiderSignal:
    score: float
    buy_shares: float
    sell_shares: float
    transaction_count: int
    transactions: list[InsiderTransaction] = field(default_factory=list)
    error: str | None = None


# ── XML helpers ───────────────────────────────────────────────────────────────

def _text(element: ET.Element | None, *paths: str) -> str | None:
    """Find the first matching path and return its text (tries each path in order)."""
    if element is None:
        return None
    for path in paths:
        node = element.find(path)
        if node is not None and node.text and node.text.strip():
            return node.text.strip()
    return None


def _parse_transactions(root: ET.Element, table_tag: str, code_path: str) -> list[dict]:
    """Extract transactions from either the non-derivative or derivative table."""
    owner_name  = _text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown"
    owner_title = (
        _text(root, ".//reportingOwner/reportingOwnerRelationship/officerTitle")
        or ("Director" if _text(root, ".//reportingOwnerRelationship/isDirector") == "1" else "")
    )

    results = []
    for txn in root.findall(f".//{table_tag}"):
        date_str  = _text(txn, "transactionDate/value", "transactionDate")
        code      = _text(txn, code_path)
        shares_str = _text(txn,
            "transactionAmounts/transactionShares/value",
            "transactionAmounts/transactionShares",
        )
        price_str = _text(txn,
            "transactionAmounts/transactionPricePerShare/value",
            "transactionAmounts/transactionPricePerShare",
        )

        if not date_str or not code or not shares_str:
            continue
        try:
            shares = float(shares_str)
            price  = float(price_str) if price_str else None
        except ValueError:
            continue

        results.append({
            "name": owner_name, "title": owner_title,
            "code": code.upper(), "shares": shares,
            "price": price, "date": date_str,
        })
    return results


def _parse_form4_xml(xml_bytes: bytes) -> list[dict]:
    """Extract all insider transactions from a Form 4 XML document."""
    try:
        # Strip namespace declarations which break find() paths
        xml_str = xml_bytes.decode("utf-8", errors="replace")
        xml_str = xml_str[xml_str.find("<"):]  # drop any BOM / preamble
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        logger.debug("sec_insider: XML parse error: %s", exc)
        return []

    txns = []
    # Non-derivative table: direct open-market purchases and sales
    txns += _parse_transactions(root, "nonDerivativeTransaction",
                                "transactionCoding/transactionCode")
    # Derivative table: RSUs, options, warrants — also signals insider conviction
    txns += _parse_transactions(root, "derivativeTransaction",
                                "transactionCoding/transactionCode")
    return txns


# ── Main tracker ──────────────────────────────────────────────────────────────

class InsiderTracker:
    """Fetches and scores SEC Form 4 insider trades for watched tickers."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._cache: dict[str, tuple[InsiderSignal, float]] = {}

    def get_insider_signal(self, ticker: str) -> InsiderSignal:
        ticker = ticker.upper()
        cached = self._cache.get(ticker)
        if cached and time.time() - cached[1] < _CACHE_TTL:
            return cached[0]
        signal = self._fetch_and_score(ticker)
        self._cache[ticker] = (signal, time.time())
        return signal

    def _fetch_and_score(self, ticker: str) -> InsiderSignal:
        _load_cik_map()
        cik = _cik_map.get(ticker)
        if not cik:
            return InsiderSignal(score=0.0, buy_shares=0, sell_shares=0,
                                 transaction_count=0, error=f"No CIK for {ticker}")

        filings = self._recent_form4_filings(cik)
        if not filings:
            logger.debug("sec_insider: no Form 4 filings found for %s (CIK %s)", ticker, cik)
            return InsiderSignal(score=0.0, buy_shares=0, sell_shares=0, transaction_count=0)

        cutoff  = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)
        raw_txns: list[dict] = []
        for accession, primary_doc in filings[:_MAX_FILINGS]:
            xml_bytes = self._fetch_filing_xml(cik, accession, primary_doc)
            if xml_bytes:
                parsed = _parse_form4_xml(xml_bytes)
                logger.debug("sec_insider: %s filing %s → %d txns", ticker, accession, len(parsed))
                raw_txns.extend(parsed)

        return self._score(raw_txns, cutoff)

    def _recent_form4_filings(self, cik: str) -> list[tuple[str, str]]:
        """Return (accessionNumber, primaryDocument) for recent Form 4 / 4/A filings."""
        url = f"{_EDGAR_BASE}/submissions/CIK{cik}.json"
        try:
            resp = self._session.get(url, timeout=8)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("sec_insider: submissions fetch failed CIK %s: %s", cik, exc)
            return []

        recent  = resp.json().get("filings", {}).get("recent", {})
        cutoff  = (datetime.now() - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

        return [
            (acc, doc)
            for form, date, acc, doc in zip(
                recent.get("form", []),
                recent.get("filingDate", []),
                recent.get("accessionNumber", []),
                recent.get("primaryDocument", []),
            )
            if form in ("4", "4/A") and date >= cutoff
        ]

    def _fetch_filing_xml(self, cik: str, accession: str, primary_doc: str) -> bytes | None:
        """Fetch Form 4 XML. If the primary doc is .htm, try swapping to .xml."""
        acc_nodash = accession.replace("-", "")
        base = f"{_ARCHIVE_BASE}/{int(cik)}/{acc_nodash}"

        candidates = [primary_doc]
        if not primary_doc.lower().endswith(".xml"):
            stem = primary_doc.rsplit(".", 1)[0]
            candidates.insert(0, f"{stem}.xml")

        for doc in candidates:
            try:
                resp = self._session.get(f"{base}/{doc}", timeout=8)
                if resp.status_code == 200:
                    content_type = resp.headers.get("Content-Type", "")
                    if "html" in content_type and doc == candidates[-1]:
                        logger.debug("sec_insider: %s is HTML, skipping", doc)
                        return None
                    return resp.content
            except Exception as exc:
                logger.debug("sec_insider: fetch failed %s/%s: %s", base, doc, exc)

        return None

    @staticmethod
    def _score(raw_txns: list[dict], cutoff: datetime) -> InsiderSignal:
        now = datetime.now(timezone.utc)
        buy_shares = sell_shares = 0.0
        transactions: list[InsiderTransaction] = []

        for t in raw_txns:
            try:
                date = datetime.fromisoformat(t["date"]).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if date < cutoff:
                continue

            code     = t["code"]
            days_ago = max(0, (now - date).days)

            # P = open-market purchase, A = acquisition (RSU vest / award)
            # S = open-market sale,     D = disposition
            if code in ("P", "A"):
                txn_type    = "Buy"
                buy_shares += t["shares"]
            elif code in ("S", "D"):
                txn_type     = "Sell"
                sell_shares += t["shares"]
            else:
                txn_type = "Other"

            price = t.get("price")
            value = round(t["shares"] * price, 2) if price else None

            transactions.append(InsiderTransaction(
                name=t["name"], title=t["title"],
                transaction_type=txn_type, shares=t["shares"],
                price=price, value=value, date=t["date"], days_ago=days_ago,
            ))

        total = buy_shares + sell_shares
        score = round((buy_shares - sell_shares) / total, 4) if total > 0 else 0.0
        transactions.sort(key=lambda x: x.date, reverse=True)

        return InsiderSignal(
            score=score, buy_shares=buy_shares, sell_shares=sell_shares,
            transaction_count=len(transactions), transactions=transactions,
        )

    def to_dict(self, signal: InsiderSignal) -> dict:
        return {
            "score": signal.score,
            "buy_shares": signal.buy_shares,
            "sell_shares": signal.sell_shares,
            "transaction_count": signal.transaction_count,
            "error": signal.error,
            "transactions": [
                {
                    "name": t.name, "title": t.title, "type": t.transaction_type,
                    "shares": t.shares, "price": t.price, "value": t.value,
                    "date": t.date, "days_ago": t.days_ago,
                }
                for t in signal.transactions[:10]
            ],
        }
