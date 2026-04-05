"""Track politician stock trades by scraping Capitol Trades and public disclosures."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from trading_algorithm.config import (
    CAPITOL_TRADES_URL,
    TRACKED_POLITICIANS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


@dataclass
class PoliticianTrade:
    """Represents a single politician stock transaction."""

    politician: str
    ticker: str
    trade_type: str  # "buy" or "sell"
    amount_range: str  # e.g. "$1,001 - $15,000"
    trade_date: datetime
    disclosure_date: datetime
    chamber: str  # "Senate" or "House"
    party: str

    @property
    def is_buy(self) -> bool:
        return self.trade_type.lower() in ("buy", "purchase")

    @property
    def is_sell(self) -> bool:
        return self.trade_type.lower() in ("sell", "sale", "sale (full)", "sale (partial)")

    @property
    def estimated_amount(self) -> float:
        """Parse the midpoint of the amount range."""
        try:
            cleaned = self.amount_range.replace("$", "").replace(",", "")
            parts = cleaned.split("-")
            if len(parts) == 2:
                low = float(parts[0].strip())
                high = float(parts[1].strip())
                return (low + high) / 2
            return float(parts[0].strip())
        except (ValueError, IndexError):
            return 0.0


@dataclass
class PoliticianSentiment:
    """Aggregated signal from politician trading activity for a ticker."""

    ticker: str
    buy_count: int = 0
    sell_count: int = 0
    total_estimated_buy_volume: float = 0.0
    total_estimated_sell_volume: float = 0.0
    notable_traders: list[str] = field(default_factory=list)
    recent_trades: list[PoliticianTrade] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def signal_score(self) -> float:
        """Score from -1.0 (all selling) to +1.0 (all buying).

        Weighted by estimated trade volume.
        """
        total_volume = self.total_estimated_buy_volume + self.total_estimated_sell_volume
        if total_volume == 0:
            if self.buy_count == 0 and self.sell_count == 0:
                return 0.0
            total = self.buy_count + self.sell_count
            return (self.buy_count - self.sell_count) / total

        net = self.total_estimated_buy_volume - self.total_estimated_sell_volume
        return max(-1.0, min(1.0, net / total_volume))


class PoliticalTradeTracker:
    """Scrapes Capitol Trades for recent politician stock transactions."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._trade_cache: list[PoliticianTrade] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=15)  # Don't hammer the site

    def fetch_recent_trades(self, force: bool = False) -> list[PoliticianTrade]:
        """Fetch recent politician trades from Capitol Trades.

        Results are cached for 15 minutes to avoid excessive scraping.
        """
        if (
            not force
            and self._last_fetch
            and datetime.now() - self._last_fetch < self._cache_ttl
        ):
            return self._trade_cache

        trades = []

        # Try Capitol Trades
        try:
            trades.extend(self._scrape_capitol_trades())
        except Exception as exc:
            logger.warning("Capitol Trades scrape failed: %s", exc)

        # Fallback / supplement: try House/Senate disclosure RSS
        try:
            trades.extend(self._scrape_disclosure_feeds())
        except Exception as exc:
            logger.warning("Disclosure feed scrape failed: %s", exc)

        if trades:
            self._trade_cache = trades
            self._last_fetch = datetime.now()

        return self._trade_cache

    def get_ticker_signal(self, ticker: str) -> PoliticianSentiment:
        """Get aggregated politician trading signal for a specific ticker."""
        trades = self.fetch_recent_trades()
        relevant = [t for t in trades if t.ticker.upper() == ticker.upper()]

        sentiment = PoliticianSentiment(ticker=ticker)
        seen_politicians = set()

        for trade in relevant:
            if trade.is_buy:
                sentiment.buy_count += 1
                sentiment.total_estimated_buy_volume += trade.estimated_amount
            elif trade.is_sell:
                sentiment.sell_count += 1
                sentiment.total_estimated_sell_volume += trade.estimated_amount

            if trade.politician not in seen_politicians:
                seen_politicians.add(trade.politician)
                sentiment.notable_traders.append(trade.politician)

        sentiment.recent_trades = relevant[:10]  # Keep last 10
        sentiment.last_updated = datetime.now()
        return sentiment

    def get_all_signals(self, tickers: list[str]) -> dict[str, PoliticianSentiment]:
        """Get politician signals for multiple tickers."""
        # Fetch once, then filter
        self.fetch_recent_trades()
        return {ticker: self.get_ticker_signal(ticker) for ticker in tickers}

    def _scrape_capitol_trades(self) -> list[PoliticianTrade]:
        """Scrape recent trades from capitoltrades.com."""
        trades = []
        try:
            resp = self.session.get(
                f"{CAPITOL_TRADES_URL}/trades",
                timeout=15,
                params={"page": 1, "pageSize": 50},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Parse trade table rows
            rows = soup.select("table tbody tr")
            for row in rows:
                try:
                    trade = self._parse_capitol_trades_row(row)
                    if trade and self._is_tracked_politician(trade.politician):
                        trades.append(trade)
                except Exception as exc:
                    logger.debug("Failed to parse row: %s", exc)
                    continue

        except requests.RequestException as exc:
            logger.warning("Request to Capitol Trades failed: %s", exc)

        return trades

    def _parse_capitol_trades_row(self, row) -> Optional[PoliticianTrade]:
        """Parse a single table row from Capitol Trades into a PoliticianTrade."""
        cells = row.select("td")
        if len(cells) < 7:
            return None

        politician_name = cells[0].get_text(strip=True)
        ticker = cells[2].get_text(strip=True).upper()
        trade_type = cells[3].get_text(strip=True).lower()
        amount_range = cells[4].get_text(strip=True)
        trade_date_str = cells[5].get_text(strip=True)
        chamber = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        # Parse date
        try:
            trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d")
        except ValueError:
            trade_date = datetime.now()

        # Skip trades older than 90 days
        if datetime.now() - trade_date > timedelta(days=90):
            return None

        return PoliticianTrade(
            politician=politician_name,
            ticker=ticker,
            trade_type=trade_type,
            amount_range=amount_range,
            trade_date=trade_date,
            disclosure_date=datetime.now(),
            chamber=chamber,
            party="",  # Would need additional parsing
        )

    def _scrape_disclosure_feeds(self) -> list[PoliticianTrade]:
        """Supplement with data from official disclosure feeds."""
        # Placeholder for additional data sources (e.g., Senate eFD, House disclosures)
        # These require parsing PDFs or structured XML which is complex.
        # For now, return empty — the Capitol Trades scraper is the primary source.
        return []

    @staticmethod
    def _is_tracked_politician(name: str) -> bool:
        """Check if a politician name matches our tracked list (fuzzy)."""
        name_lower = name.lower()
        for tracked in TRACKED_POLITICIANS:
            # Check if last name matches (handles "Rep. Pelosi" vs "Nancy Pelosi")
            last_name = tracked.split()[-1].lower()
            if last_name in name_lower:
                return True
        return False
