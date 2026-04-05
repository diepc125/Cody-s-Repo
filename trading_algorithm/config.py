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

# ─── News / sentiment sources ──────────────────────────────
RSS_FEEDS = [
    # General financial news
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
    # MarketWatch
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    # CNBC
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    # Reuters Business
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
]

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
