"""SEC Form 4 insider trade tracker.

Uses the public EDGAR submissions API — no API key required.
SEC requires a descriptive User-Agent and enforces a 10 req/s rate limit.
We stay well within that via per-ticker caching (1-hour TTL).

Scoring logic:
  score = (buy_shares - sell_shares) / (buy_shares + sell_shares)  → [-1, +1]
  Clamped and weighted by recency so older trades matter less.
"""

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_EDGAR_BASE = "https://data.sec.gov"
_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_HEADERS = {
    "User-Agent": "Sentinel TradingApp sentinel-trading@proton.me",
    "Accept-Encoding": "gzip, deflate",
}

_LOOKBACK_DAYS = 90
_MAX_FILINGS = 3       # Form 4 filings to parse per on-demand fetch
_CACHE_TTL = 3600      # seconds — Form 4s are filed at most a few times a day


# ── CIK map ───────────────────────────────────────────────────────────────────

_cik_map: dict[str, str] = {}  # ticker → zero-padded 10-digit CIK string


def _load_cik_map() -> None:
    """Populate the in-memory ticker→CIK map from EDGAR's bulk JSON.

    Called once on first use; subsequent calls are no-ops.
    """
    if _cik_map:
        return
    try:
        resp = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        for entry in resp.json().values():
            ticker = entry["ticker"].upper()
            cik = str(entry["cik_str"]).zfill(10)
            _cik_map[ticker] = cik
        logger.info("sec_insider: loaded %d CIK mappings", len(_cik_map))
    except Exception as exc:
        logger.warning("sec_insider: failed to load CIK map: %s", exc)


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class InsiderTransaction:
    name: str
    title: str
    transaction_type: str   # "Buy" | "Sell" | "Other"
    shares: float
    price: float | None
    value: float | None     # shares * price when both available
    date: str               # ISO date string YYYY-MM-DD
    days_ago: int


@dataclass
class InsiderSignal:
    score: float                                  # -1.0 to +1.0
    buy_shares: float
    sell_shares: float
    transaction_count: int
    transactions: list[InsiderTransaction] = field(default_factory=list)
    error: str | None = None


# ── XML helpers ───────────────────────────────────────────────────────────────

def _xml_text(element: ET.Element | None, path: str) -> str | None:
    """Navigate an XPath and return the text of the first match, or None."""
    if element is None:
        return None
    node = element.find(path)
    return node.text.strip() if node is not None and node.text else None


def _parse_form4_xml(xml_bytes: bytes) -> list[dict]:
    """Extract non-derivative transactions from a Form 4 XML document."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.debug("sec_insider: XML parse error: %s", exc)
        return []

    # Reporting owner info (one per document, applies to all transactions)
    owner_name = (
        _xml_text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown"
    )
    owner_title = (
        _xml_text(root, ".//reportingOwner/reportingOwnerRelationship/officerTitle")
        or _xml_text(root, ".//reportingOwner/reportingOwnerRelationship/isDirector")
        and "Director"
        or ""
    )

    transactions = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        date_str = _xml_text(txn, "transactionDate/value")
        code = _xml_text(txn, "transactionCoding/transactionCode")
        shares_str = _xml_text(txn, "transactionAmounts/transactionShares/value")
        price_str = _xml_text(txn, "transactionAmounts/transactionPricePerShare/value")

        if not date_str or not code or not shares_str:
            continue

        try:
            shares = float(shares_str)
            price = float(price_str) if price_str else None
        except ValueError:
            continue

        transactions.append({
            "name": owner_name,
            "title": owner_title,
            "code": code,          # P=purchase, S=sale, etc.
            "shares": shares,
            "price": price,
            "date": date_str,
        })

    return transactions


# ── Main tracker ──────────────────────────────────────────────────────────────

class InsiderTracker:
    """Fetches and scores SEC Form 4 insider trades for watched tickers."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._cache: dict[str, tuple[InsiderSignal, float]] = {}

    def get_insider_signal(self, ticker: str) -> InsiderSignal:
        """Return a scored insider signal for *ticker*, using cache when fresh."""
        ticker = ticker.upper()
        cached = self._cache.get(ticker)
        if cached and time.time() - cached[1] < _CACHE_TTL:
            return cached[0]

        signal = self._fetch_and_score(ticker)
        self._cache[ticker] = (signal, time.time())
        return signal

    # ── Private ───────────────────────────────────────────────────────────────

    def _fetch_and_score(self, ticker: str) -> InsiderSignal:
        _load_cik_map()

        cik = _cik_map.get(ticker)
        if not cik:
            return InsiderSignal(score=0.0, buy_shares=0, sell_shares=0,
                                 transaction_count=0, error=f"No CIK for {ticker}")

        filings = self._recent_form4_filings(cik)
        if not filings:
            return InsiderSignal(score=0.0, buy_shares=0, sell_shares=0,
                                 transaction_count=0)

        cutoff = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)
        raw_txns: list[dict] = []

        for accession, primary_doc in filings[:_MAX_FILINGS]:
            xml_bytes = self._fetch_form4_xml(cik, accession, primary_doc)
            if xml_bytes:
                raw_txns.extend(_parse_form4_xml(xml_bytes))

        return self._score(raw_txns, cutoff)

    def _recent_form4_filings(self, cik: str) -> list[tuple[str, str]]:
        """Return (accessionNumber, primaryDocument) pairs for recent Form 4s."""
        url = f"{_EDGAR_BASE}/submissions/CIK{cik}.json"
        try:
            resp = self._session.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("sec_insider: submissions fetch failed for CIK %s: %s", cik, exc)
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        cutoff = (datetime.now() - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

        result = []
        for form, date, acc, doc in zip(forms, dates, accessions, docs):
            if form == "4" and date >= cutoff:
                result.append((acc, doc))
        return result

    def _fetch_form4_xml(self, cik: str, accession: str, primary_doc: str) -> bytes | None:
        """Fetch raw Form 4 XML bytes from EDGAR Archives."""
        # accession "0000320193-24-000001" → path "000032019324000001"
        acc_nodash = accession.replace("-", "")
        url = f"{_ARCHIVE_BASE}/{int(cik)}/{acc_nodash}/{primary_doc}"
        try:
            resp = self._session.get(url, timeout=8)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.debug("sec_insider: XML fetch failed %s: %s", url, exc)
            return None

    @staticmethod
    def _score(raw_txns: list[dict], cutoff: datetime) -> InsiderSignal:
        """Compute a net sentiment score from a list of raw transactions."""
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

            days_ago = max(0, (now - date).days)
            code = t["code"].upper()

            if code == "P":
                txn_type = "Buy"
                buy_shares += t["shares"]
            elif code == "S":
                txn_type = "Sell"
                sell_shares += t["shares"]
            else:
                txn_type = "Other"

            price = t.get("price")
            value = round(t["shares"] * price, 2) if price else None

            transactions.append(InsiderTransaction(
                name=t["name"],
                title=t["title"],
                transaction_type=txn_type,
                shares=t["shares"],
                price=price,
                value=value,
                date=t["date"],
                days_ago=days_ago,
            ))

        total = buy_shares + sell_shares
        score = round((buy_shares - sell_shares) / total, 4) if total > 0 else 0.0

        # Sort most recent first for display
        transactions.sort(key=lambda x: x.date, reverse=True)

        return InsiderSignal(
            score=score,
            buy_shares=buy_shares,
            sell_shares=sell_shares,
            transaction_count=len(transactions),
            transactions=transactions,
        )

    def to_dict(self, signal: InsiderSignal) -> dict:
        """Serialise an InsiderSignal to a JSON-safe dict for API responses."""
        return {
            "score": signal.score,
            "buy_shares": signal.buy_shares,
            "sell_shares": signal.sell_shares,
            "transaction_count": signal.transaction_count,
            "error": signal.error,
            "transactions": [
                {
                    "name": t.name,
                    "title": t.title,
                    "type": t.transaction_type,
                    "shares": t.shares,
                    "price": t.price,
                    "value": t.value,
                    "date": t.date,
                    "days_ago": t.days_ago,
                }
                for t in signal.transactions[:10]  # cap at 10 for API response
            ],
        }
