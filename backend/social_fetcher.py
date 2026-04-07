"""Reddit and StockTwits social sentiment fetcher.

Reddit: Uses public JSON API (no auth needed for read-only).
StockTwits: Public API with user-labeled bullish/bearish sentiment.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from trading_algorithm.config import USER_AGENT

logger = logging.getLogger(__name__)

REDDIT_HEADERS = {
    "User-Agent": "SentinelTradingBot/1.0 (sentiment research)",
}

STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"
REDDIT_BASE = "https://www.reddit.com"

# Fewer subreddits = fewer requests. WSB + stocks covers the bulk of signal.
REDDIT_SUBS = ["wallstreetbets", "stocks", "investing"]

# Module-level backoff: when Reddit 429s us, all tickers wait until this time.
_reddit_blocked_until: float = 0.0
_REDDIT_BACKOFF_SECONDS = 120  # wait 2 minutes after a 429


class RedditFetcher:
    """Fetches posts mentioning a ticker from financial subreddits."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REDDIT_HEADERS)
        self._cache: dict[str, tuple[list, float]] = {}
        self._cache_ttl = 900  # 15 minutes — Reddit rate limits anonymous access hard

    def fetch_ticker_posts(self, ticker: str, max_posts: int = 30) -> list[dict]:
        """Fetch Reddit posts that are specifically about *ticker*.

        Strategy:
        1. Search each subreddit for the cashtag ($AAPL) — highest precision
        2. Also search for the bare ticker symbol
        3. Keep only posts where the title contains the cashtag or ticker symbol
           so that passing mentions in unrelated threads are excluded
        """
        ticker = ticker.upper()
        cache_key = ticker
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        global _reddit_blocked_until

        posts: list[dict] = []
        seen_ids: set[str] = set()

        # Single combined query: "AAPL OR $AAPL" — one request per subreddit
        # instead of two, cutting request count in half.
        query = f"{ticker} OR ${ticker}"

        for sub in REDDIT_SUBS:
            if time.time() < _reddit_blocked_until:
                break  # whole module is in backoff — skip remaining subs

            try:
                url = f"{REDDIT_BASE}/r/{sub}/search.json"
                params = {
                    "q": query,
                    "sort": "relevance",
                    "limit": 10,
                    "restrict_sr": "true",
                    "t": "week",
                }
                resp = self.session.get(url, params=params, timeout=10)

                if resp.status_code == 429:
                    _reddit_blocked_until = time.time() + _REDDIT_BACKOFF_SECONDS
                    logger.warning(
                        "Reddit rate limited — pausing all Reddit fetches for %ds",
                        _REDDIT_BACKOFF_SECONDS,
                    )
                    break

                if not resp.ok:
                    continue

                for child in resp.json().get("data", {}).get("children", []):
                    post = child.get("data", {})
                    post_id = post.get("id")
                    if not post_id or post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    title = post.get("title", "")
                    if not self._title_is_about(title, ticker):
                        continue

                    created = post.get("created_utc", 0)
                    if time.time() - created > 604800:  # 7 days
                        continue

                    posts.append({
                        "title":        title,
                        "body":         post.get("selftext", "")[:500],
                        "score":        post.get("score", 0),
                        "upvote_ratio": post.get("upvote_ratio", 0.5),
                        "created_utc":  created,
                        "subreddit":    sub,
                        "url":          f"https://reddit.com{post.get('permalink', '')}",
                        "num_comments": post.get("num_comments", 0),
                        "source":       "reddit",
                    })
            except Exception as exc:
                logger.warning("Reddit fetch failed r/%s %s: %s", sub, ticker, exc)

        posts.sort(key=lambda p: p["score"], reverse=True)
        posts = posts[:max_posts]
        self._cache[cache_key] = (posts, time.time())
        return posts

    @staticmethod
    def _title_is_about(title: str, ticker: str) -> bool:
        """True if the post title contains the ticker symbol or cashtag."""
        t = title.lower()
        return (
            f"${ticker.lower()}" in t
            or f" {ticker.lower()} " in t
            or t.startswith(f"{ticker.lower()} ")
            or t.endswith(f" {ticker.lower()}")
        )

    def get_texts_for_sentiment(self, ticker: str) -> list[str]:
        """Return combined title+body strings for sentiment analysis."""
        posts = self.fetch_ticker_posts(ticker)
        texts = []
        for p in posts:
            text = p["title"]
            if p["body"] and p["body"] != "[removed]":
                text += f". {p['body'][:200]}"
            texts.append(text)
        return texts

    def get_summary(self, ticker: str) -> dict:
        """Return a summary of Reddit activity for a ticker."""
        posts = self.fetch_ticker_posts(ticker)
        if not posts:
            return {"post_count": 0, "avg_score": 0, "top_posts": [], "subreddits": []}

        avg_score = sum(p["score"] for p in posts) / len(posts)
        subs_seen = list({p["subreddit"] for p in posts})
        top_posts = [
            {"title": p["title"], "score": p["score"], "subreddit": p["subreddit"], "url": p["url"]}
            for p in posts[:5]
        ]

        return {
            "post_count": len(posts),
            "avg_score": round(avg_score, 1),
            "top_posts": top_posts,
            "subreddits": subs_seen,
        }


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://stocktwits.com/",
    "Origin": "https://stocktwits.com",
}


class StockTwitsFetcher:
    """Fetches messages from StockTwits with user-labeled sentiment."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_BROWSER_HEADERS)
        self._cache: dict[str, tuple[list, float]] = {}
        self._cache_ttl = 120  # 2 minutes
        self._blocked = False   # set True on first 403; stops retrying

    def fetch_ticker_messages(self, ticker: str, max_messages: int = 30) -> list[dict]:
        """Fetch recent StockTwits messages for a ticker.

        Returns list of dicts with: body, sentiment (bullish/bearish/None),
        created_at, username, likes.
        """
        if self._blocked:
            return []

        cache_key = ticker.upper()
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        messages = []
        try:
            url = f"{STOCKTWITS_BASE}/streams/symbol/{ticker.upper()}.json"
            resp = self.session.get(url, timeout=10, params={"limit": max_messages})
            if resp.status_code == 403:
                logger.info("StockTwits API requires auth — disabling (Reddit-only mode)")
                self._blocked = True
                return []
            if resp.status_code == 429:
                logger.warning("StockTwits rate limited for %s", ticker)
                return []
            resp.raise_for_status()
            data = resp.json()

            for msg in data.get("messages", []):
                sentiment = None
                entities = msg.get("entities", {})
                sentiment_data = entities.get("sentiment", {})
                if sentiment_data:
                    sentiment = sentiment_data.get("basic", "").lower() or None

                messages.append({
                    "body": msg.get("body", ""),
                    "sentiment": sentiment,  # "bullish", "bearish", or None
                    "created_at": msg.get("created_at", ""),
                    "username": msg.get("user", {}).get("username", ""),
                    "likes": msg.get("likes", {}).get("total", 0),
                    "source": "stocktwits",
                })
        except Exception as exc:
            logger.warning("StockTwits fetch failed for %s: %s", ticker, exc)

        self._cache[cache_key] = (messages, time.time())
        return messages

    def get_labeled_sentiment(self, ticker: str) -> dict:
        """Return bullish/bearish counts from user-labeled StockTwits messages.

        StockTwits users manually tag their messages as bullish or bearish,
        making this a unique direct signal.
        """
        messages = self.fetch_ticker_messages(ticker)
        bullish = sum(1 for m in messages if m["sentiment"] == "bullish")
        bearish = sum(1 for m in messages if m["sentiment"] == "bearish")
        unlabeled = len(messages) - bullish - bearish

        total_labeled = bullish + bearish
        if total_labeled > 0:
            bull_ratio = bullish / total_labeled
            # Map to -1..+1: 50% bull = 0, 100% bull = +1, 0% bull = -1
            score = (bull_ratio - 0.5) * 2
        else:
            score = 0.0

        return {
            "bullish": bullish,
            "bearish": bearish,
            "unlabeled": unlabeled,
            "total": len(messages),
            "bull_ratio": round(bull_ratio if total_labeled > 0 else 0.5, 3),
            "score": round(score, 4),
        }

    def get_texts_for_sentiment(self, ticker: str) -> list[str]:
        """Return raw message bodies for FinBERT/VADER analysis."""
        messages = self.fetch_ticker_messages(ticker)
        return [m["body"] for m in messages if m["body"]]


class SocialSentimentAggregator:
    """Combines Reddit + StockTwits into a unified social sentiment signal."""

    def __init__(self):
        self.reddit = RedditFetcher()
        self.stocktwits = StockTwitsFetcher()

    def get_social_signal(
        self,
        ticker: str,
        sentiment_analyzer=None,
    ) -> dict:
        """Return a unified social sentiment dict for a ticker.

        Args:
            ticker: Stock symbol
            sentiment_analyzer: SentimentAnalyzer instance (FinBERT or VADER)

        Returns dict with:
            score: float -1.0 to +1.0 (composite social sentiment)
            reddit_score: float (from NLP on Reddit posts)
            stocktwits_score: float (from user labels + NLP)
            post_count: int
            message_count: int
            bull_ratio: float (StockTwits)
            top_posts: list
        """
        # Reddit NLP sentiment
        reddit_texts = self.reddit.get_texts_for_sentiment(ticker)
        reddit_score = 0.0
        reddit_count = len(reddit_texts)
        if reddit_texts and sentiment_analyzer:
            reddit_score, _ = sentiment_analyzer.analyze_social_texts(reddit_texts)

        # StockTwits: combine user labels + NLP
        st_labeled = self.stocktwits.get_labeled_sentiment(ticker)
        st_texts = self.stocktwits.get_texts_for_sentiment(ticker)
        st_nlp_score = 0.0
        if st_texts and sentiment_analyzer:
            st_nlp_score, _ = sentiment_analyzer.analyze_social_texts(st_texts)

        # StockTwits final: 60% user labels (ground truth) + 40% NLP
        st_score = (st_labeled["score"] * 0.6) + (st_nlp_score * 0.4)

        # Combined: weight by data availability
        reddit_weight = 0.4 if reddit_count > 0 else 0
        st_weight = 0.6 if st_labeled["total"] > 0 else 0
        total_weight = reddit_weight + st_weight

        if total_weight > 0:
            composite = (
                (reddit_score * reddit_weight) + (st_score * st_weight)
            ) / total_weight
        else:
            composite = 0.0

        reddit_summary = self.reddit.get_summary(ticker)

        return {
            "score": round(composite, 4),
            "reddit_score": round(reddit_score, 4),
            "stocktwits_score": round(st_score, 4),
            "stocktwits_labeled_score": round(st_labeled["score"], 4),
            "post_count": reddit_count,
            "message_count": st_labeled["total"],
            "bull_ratio": st_labeled["bull_ratio"],
            "bullish_count": st_labeled["bullish"],
            "bearish_count": st_labeled["bearish"],
            "top_posts": reddit_summary.get("top_posts", []),
            "subreddits": reddit_summary.get("subreddits", []),
        }
