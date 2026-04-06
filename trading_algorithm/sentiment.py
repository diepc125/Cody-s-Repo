"""Sentiment analysis engine — FinBERT (GPU) with VADER fallback."""

import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# Try to load FinBERT from the backend module
_finbert = None

def _try_load_finbert():
    global _finbert
    if _finbert is not None:
        return _finbert
    try:
        backend_path = str(Path(__file__).resolve().parent.parent / "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        from finbert import get_finbert
        instance = get_finbert()
        if instance.ready:
            _finbert = instance
            logger.info(
                "Sentiment engine: FinBERT on %s (CUDA %s)",
                instance.device_name,
                instance.cuda_version or "N/A",
            )
        else:
            logger.info("FinBERT not ready — using VADER")
    except Exception as exc:
        logger.info("FinBERT unavailable (%s) — using VADER", exc)
    return _finbert


@dataclass
class SentimentResult:
    text: str
    compound: float       # -1.0 to +1.0
    positive: float
    negative: float
    neutral: float
    engine: str = "vader"  # "vader" or "finbert"
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AggregateSentiment:
    ticker: str
    news_score: float = 0.0
    social_score: float = 0.0
    article_count: int = 0
    social_mention_count: int = 0
    top_headlines: list[str] = field(default_factory=list)
    engine: str = "vader"
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def combined_score(self) -> float:
        total = self.article_count + self.social_mention_count
        if total == 0:
            return 0.0
        nw = self.article_count / total
        sw = self.social_mention_count / total
        return (self.news_score * nw) + (self.social_score * sw)


class SentimentAnalyzer:
    """Sentiment analysis with FinBERT on GPU, falling back to VADER."""

    FINANCIAL_BOOSTERS = {
        "upgrade": 0.4, "beat": 0.3, "beats": 0.3,
        "surpass": 0.3, "surpasses": 0.3, "outperform": 0.4,
        "bullish": 0.5, "rally": 0.4, "soar": 0.5, "soars": 0.5,
        "surge": 0.4, "surges": 0.4, "breakout": 0.3,
        "record high": 0.4, "all-time high": 0.5,
        "strong earnings": 0.4, "dividend increase": 0.3,
        "buyback": 0.3, "acquisition": 0.2,
        "downgrade": -0.4, "miss": -0.3, "misses": -0.3,
        "underperform": -0.4, "bearish": -0.5,
        "crash": -0.5, "crashes": -0.5, "plunge": -0.5, "plunges": -0.5,
        "selloff": -0.4, "sell-off": -0.4, "bankruptcy": -0.6,
        "default": -0.4, "layoffs": -0.3, "lawsuit": -0.3,
        "investigation": -0.3, "fraud": -0.5, "scandal": -0.4,
        "recession": -0.4, "inflation": -0.2,
        "rate hike": -0.2, "debt ceiling": -0.3,
    }

    def __init__(self):
        # VADER — always available as fallback
        self._vader = SentimentIntensityAnalyzer()
        for term, score in self.FINANCIAL_BOOSTERS.items():
            self._vader.lexicon[term] = score * 4

        # Attempt to load FinBERT
        self._finbert = _try_load_finbert()

    @property
    def engine(self) -> str:
        return "finbert" if (self._finbert and self._finbert.ready) else "vader"

    def analyze_text(self, text: str) -> SentimentResult:
        """Analyze a single text. Uses FinBERT if available, else VADER."""
        cleaned = self._clean_text(text)

        if self._finbert and self._finbert.ready:
            result = self._finbert.analyze(cleaned)
            if result:
                return SentimentResult(
                    text=text[:200],
                    compound=result.score,
                    positive=result.positive_prob,
                    negative=result.negative_prob,
                    neutral=result.neutral_prob,
                    engine="finbert",
                )

        # VADER fallback
        scores = self._vader.polarity_scores(cleaned)
        return SentimentResult(
            text=text[:200],
            compound=scores["compound"],
            positive=scores["pos"],
            negative=scores["neg"],
            neutral=scores["neu"],
            engine="vader",
        )

    def analyze_articles(self, articles: list[dict]) -> AggregateSentiment:
        """Score a batch of news articles. Uses FinBERT batch inference on GPU."""
        if not articles:
            return AggregateSentiment(ticker="UNKNOWN")

        headlines = [a.get("title", "") for a in articles]

        # FinBERT batch path — much faster than looping
        if self._finbert and self._finbert.ready:
            texts = [
                f"{a.get('title', '')}. {a.get('summary', '')}"
                for a in articles
            ]
            cleaned = [self._clean_text(t) for t in texts]
            avg_score, count = self._finbert.score_texts(cleaned)
            if count > 0:
                return AggregateSentiment(
                    ticker="",
                    news_score=avg_score,
                    article_count=count,
                    top_headlines=headlines[:5],
                    engine="finbert",
                    last_updated=datetime.now(),
                )

        # VADER fallback
        scores = []
        for article in articles:
            text = f"{article.get('title', '')}. {article.get('summary', '')}"
            result = self.analyze_text(text)
            scores.append(result.compound)

        avg = sum(scores) / len(scores) if scores else 0.0
        return AggregateSentiment(
            ticker="",
            news_score=round(avg, 4),
            article_count=len(scores),
            top_headlines=headlines[:5],
            engine="vader",
            last_updated=datetime.now(),
        )

    def analyze_social_texts(self, texts: list[str]) -> tuple[float, int]:
        """Score social media texts. Batch GPU inference if FinBERT available."""
        if not texts:
            return 0.0, 0

        if self._finbert and self._finbert.ready:
            cleaned = [self._clean_text(t) for t in texts]
            return self._finbert.score_texts(cleaned)

        scores = [self.analyze_text(t).compound for t in texts]
        avg = sum(scores) / len(scores) if scores else 0.0
        return round(avg, 4), len(scores)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\$[A-Z]{1,5}", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


class SentimentTracker:
    """Tracks sentiment history over time for trend detection."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: dict[str, list[AggregateSentiment]] = {}

    def update(self, ticker: str, sentiment: AggregateSentiment):
        sentiment.ticker = ticker
        if ticker not in self._history:
            self._history[ticker] = []
        self._history[ticker].append(sentiment)
        if len(self._history[ticker]) > self.max_history:
            self._history[ticker] = self._history[ticker][-self.max_history:]

    def get_trend(self, ticker: str, window: int = 10) -> Optional[float]:
        history = self._history.get(ticker, [])
        if len(history) < 2:
            return None
        recent = history[-window:]
        if len(recent) < 2:
            return None
        mid = len(recent) // 2
        first_half = [s.combined_score for s in recent[:mid]]
        second_half = [s.combined_score for s in recent[mid:]]
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        return round(avg_second - avg_first, 4)

    def get_latest(self, ticker: str) -> Optional[AggregateSentiment]:
        history = self._history.get(ticker, [])
        return history[-1] if history else None
