"""Sentiment analysis engine using VADER and aggregated news scoring."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Holds the sentiment analysis result for a single text."""

    text: str
    compound: float  # -1.0 to +1.0
    positive: float
    negative: float
    neutral: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AggregateSentiment:
    """Aggregated sentiment across multiple sources for a ticker."""

    ticker: str
    news_score: float = 0.0  # -1.0 to +1.0
    social_score: float = 0.0
    article_count: int = 0
    social_mention_count: int = 0
    top_headlines: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def combined_score(self) -> float:
        """Weighted combination of news and social sentiment."""
        if self.article_count == 0 and self.social_mention_count == 0:
            return 0.0
        total_sources = self.article_count + self.social_mention_count
        if total_sources == 0:
            return 0.0
        news_weight = self.article_count / total_sources
        social_weight = self.social_mention_count / total_sources
        return (self.news_score * news_weight) + (self.social_score * social_weight)


class SentimentAnalyzer:
    """Analyzes text sentiment using VADER, tuned for financial context."""

    # Financial-domain boosters: words that should amplify sentiment in finance
    FINANCIAL_BOOSTERS = {
        # Bullish terms
        "upgrade": 0.4,
        "beat": 0.3,
        "beats": 0.3,
        "surpass": 0.3,
        "surpasses": 0.3,
        "outperform": 0.4,
        "bullish": 0.5,
        "rally": 0.4,
        "soar": 0.5,
        "soars": 0.5,
        "surge": 0.4,
        "surges": 0.4,
        "breakout": 0.3,
        "record high": 0.4,
        "all-time high": 0.5,
        "strong earnings": 0.4,
        "dividend increase": 0.3,
        "buyback": 0.3,
        "acquisition": 0.2,
        # Bearish terms
        "downgrade": -0.4,
        "miss": -0.3,
        "misses": -0.3,
        "underperform": -0.4,
        "bearish": -0.5,
        "crash": -0.5,
        "crashes": -0.5,
        "plunge": -0.5,
        "plunges": -0.5,
        "selloff": -0.4,
        "sell-off": -0.4,
        "bankruptcy": -0.6,
        "default": -0.4,
        "layoffs": -0.3,
        "lawsuit": -0.3,
        "investigation": -0.3,
        "fraud": -0.5,
        "scandal": -0.4,
        "recession": -0.4,
        "inflation": -0.2,
        "rate hike": -0.2,
        "debt ceiling": -0.3,
    }

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        # Inject financial terms into VADER lexicon
        for term, score in self.FINANCIAL_BOOSTERS.items():
            self.analyzer.lexicon[term] = score * 4  # VADER uses ~-4 to +4

    def analyze_text(self, text: str) -> SentimentResult:
        """Analyze a single piece of text and return sentiment scores."""
        cleaned = self._clean_text(text)
        scores = self.analyzer.polarity_scores(cleaned)
        return SentimentResult(
            text=text[:200],  # Truncate for storage
            compound=scores["compound"],
            positive=scores["pos"],
            negative=scores["neg"],
            neutral=scores["neu"],
        )

    def analyze_articles(self, articles: list[dict]) -> AggregateSentiment:
        """Analyze a batch of news articles and return aggregate sentiment."""
        if not articles:
            return AggregateSentiment(ticker="UNKNOWN")

        scores = []
        headlines = []
        for article in articles:
            # Combine title and summary for richer signal
            text = f"{article.get('title', '')}. {article.get('summary', '')}"
            result = self.analyze_text(text)
            scores.append(result.compound)
            headlines.append(article.get("title", ""))

        avg_score = sum(scores) / len(scores) if scores else 0.0

        return AggregateSentiment(
            ticker="",  # Set by caller
            news_score=round(avg_score, 4),
            article_count=len(scores),
            top_headlines=headlines[:5],
            last_updated=datetime.now(),
        )

    def analyze_social_texts(self, texts: list[str]) -> tuple[float, int]:
        """Analyze a batch of social media texts (tweets, Reddit posts, etc.).

        Returns (average_compound_score, count).
        """
        if not texts:
            return 0.0, 0

        scores = []
        for text in texts:
            result = self.analyze_text(text)
            scores.append(result.compound)

        avg = sum(scores) / len(scores) if scores else 0.0
        return round(avg, 4), len(scores)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean text for better sentiment analysis."""
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Remove ticker symbols prefixed with $ (they're not sentiment)
        text = re.sub(r"\$[A-Z]{1,5}", "", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text


class SentimentTracker:
    """Tracks sentiment history over time for trend detection."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: dict[str, list[AggregateSentiment]] = {}

    def update(self, ticker: str, sentiment: AggregateSentiment):
        """Record a new sentiment reading."""
        sentiment.ticker = ticker
        if ticker not in self._history:
            self._history[ticker] = []
        self._history[ticker].append(sentiment)
        # Trim old entries
        if len(self._history[ticker]) > self.max_history:
            self._history[ticker] = self._history[ticker][-self.max_history :]

    def get_trend(self, ticker: str, window: int = 10) -> Optional[float]:
        """Calculate sentiment trend over the last `window` readings.

        Returns a value from -1 to +1 indicating direction of sentiment change.
        Positive = sentiment improving, Negative = sentiment deteriorating.
        """
        history = self._history.get(ticker, [])
        if len(history) < 2:
            return None

        recent = history[-window:]
        if len(recent) < 2:
            return None

        # Simple linear trend: compare first half avg to second half avg
        mid = len(recent) // 2
        first_half = [s.combined_score for s in recent[:mid]]
        second_half = [s.combined_score for s in recent[mid:]]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        return round(avg_second - avg_first, 4)

    def get_latest(self, ticker: str) -> Optional[AggregateSentiment]:
        """Get the most recent sentiment reading for a ticker."""
        history = self._history.get(ticker, [])
        return history[-1] if history else None
