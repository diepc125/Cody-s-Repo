"""Configuration for the trading algorithm."""

# ─── Polling ────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = 5  # how often to refresh data

# ─── Tracked stocks ────────────────────────────────────────
WATCHED_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "BAC", "DIS",
    "NFLX", "AMD", "INTC", "PFE", "XOM",
]

# ─── Politicians to track ──────────────────────────────────
TRACKED_POLITICIANS = [
    "Nancy Pelosi",
    "Donald Trump",
    "Dan Crenshaw",
    "Marjorie Taylor Greene",
    "Tommy Tuberville",
    "Michael McCaul",
    "Josh Gottheimer",
    "Mark Green",
    "Kevin Hern",
    "Ro Khanna",
]

# ─── News sources ─────────────────────────────────────────
# Only ticker-specific feeds go here — general market feeds caused every
# stock to share the same headlines regardless of relevance.
RSS_FEEDS_TICKER = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
]

# General market feeds used only for market overview, not per-ticker scoring
RSS_FEEDS_GENERAL = [
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
]

# Primary company name per ticker — used as a secondary relevance signal
# alongside the ticker symbol when filtering articles.
COMPANY_NAMES: dict[str, str] = {
    "AAPL":  "Apple",
    "MSFT":  "Microsoft",
    "GOOGL": "Google",
    "AMZN":  "Amazon",
    "TSLA":  "Tesla",
    "NVDA":  "NVIDIA",
    "META":  "Meta",
    "JPM":   "JPMorgan",
    "BAC":   "Bank of America",
    "DIS":   "Disney",
    "NFLX":  "Netflix",
    "AMD":   "AMD",
    "INTC":  "Intel",
    "PFE":   "Pfizer",
    "XOM":   "ExxonMobil",
}

# ─── Sentiment thresholds ──────────────────────────────────
# Compound VADER scores range from -1 (most negative) to +1 (most positive)
STRONG_BUY_THRESHOLD = 0.35
BUY_THRESHOLD = 0.15
SELL_THRESHOLD = -0.15
STRONG_SELL_THRESHOLD = -0.35

# ─── Signal weights ────────────────────────────────────────
# How much each component contributes to the final signal (must sum to 1.0)
WEIGHT_NEWS_SENTIMENT = 0.35
WEIGHT_SOCIAL_SENTIMENT = 0.25
WEIGHT_POLITICIAN_TRADES = 0.25
WEIGHT_PRICE_MOMENTUM = 0.15

# ─── Capitol Trades (politician tracking) ──────────────────
CAPITOL_TRADES_URL = "https://www.capitoltrades.com"

# ─── User-Agent for web requests ───────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
