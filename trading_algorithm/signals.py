"""Signal generator — combines all data sources into actionable buy/sell/hold signals."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from trading_algorithm.config import (
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_BUY_THRESHOLD,
    STRONG_SELL_THRESHOLD,
    WEIGHT_NEWS_SENTIMENT,
    WEIGHT_POLITICIAN_TRADES,
    WEIGHT_PRICE_MOMENTUM,
    WEIGHT_QUANT,
    WEIGHT_SOCIAL_SENTIMENT,
)

logger = logging.getLogger(__name__)


class Signal(Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


@dataclass
class SignalBreakdown:
    """Detailed breakdown of how a signal was computed."""

    news_sentiment_score: float = 0.0
    social_sentiment_score: float = 0.0
    politician_score: float = 0.0
    momentum_score: float = 0.0
    quant_score: float = 0.0

    news_weighted: float = 0.0
    social_weighted: float = 0.0
    politician_weighted: float = 0.0
    momentum_weighted: float = 0.0
    quant_weighted: float = 0.0


@dataclass
class StockSignal:
    """Final signal for a single stock, combining all data sources."""

    ticker: str
    signal: Signal
    composite_score: float  # -1.0 to +1.0
    confidence: float  # 0.0 to 1.0 (how much data we had)
    breakdown: SignalBreakdown
    price: Optional[float] = None
    change_pct: Optional[float] = None
    top_headlines: list[str] = field(default_factory=list)
    politician_activity: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class SignalGenerator:
    """Combines sentiment, politician trades, and price momentum into signals."""

    def generate_signal(
        self,
        ticker: str,
        news_score: float,
        social_score: float,
        politician_score: float,
        price_data: Optional[dict] = None,
        price_history: Optional[list[dict]] = None,
        article_count: int = 0,
        social_count: int = 0,
        politician_trade_count: int = 0,
        top_headlines: Optional[list[str]] = None,
        politician_summary: str = "",
        quant_score: float = 0.0,
    ) -> StockSignal:
        """Generate a composite signal for a single ticker.

        Args:
            ticker: Stock symbol
            news_score: -1.0 to +1.0 from news sentiment
            social_score: -1.0 to +1.0 from social media sentiment
            politician_score: -1.0 to +1.0 from politician trading activity
            price_data: Current price data dict
            price_history: List of OHLCV dicts for momentum calc
            article_count: Number of news articles analyzed
            social_count: Number of social posts analyzed
            politician_trade_count: Number of politician trades found
            top_headlines: Recent relevant headlines
            politician_summary: Human-readable politician activity summary
        """
        # Calculate momentum score from price history
        momentum_score = self._calculate_momentum(price_history) if price_history else 0.0

        # Build weighted composite
        breakdown = SignalBreakdown(
            news_sentiment_score=news_score,
            social_sentiment_score=social_score,
            politician_score=politician_score,
            momentum_score=momentum_score,
            quant_score=quant_score,
            news_weighted=news_score * WEIGHT_NEWS_SENTIMENT,
            social_weighted=social_score * WEIGHT_SOCIAL_SENTIMENT,
            politician_weighted=politician_score * WEIGHT_POLITICIAN_TRADES,
            momentum_weighted=momentum_score * WEIGHT_PRICE_MOMENTUM,
            quant_weighted=quant_score * WEIGHT_QUANT,
        )

        composite = (
            breakdown.news_weighted
            + breakdown.social_weighted
            + breakdown.politician_weighted
            + breakdown.momentum_weighted
            + breakdown.quant_weighted
        )

        # Clamp to [-1, 1]
        composite = max(-1.0, min(1.0, round(composite, 4)))

        # Calculate confidence based on data availability
        confidence = self._calculate_confidence(
            article_count, social_count, politician_trade_count, price_history
        )

        # Map composite score to signal
        signal = self._score_to_signal(composite)

        # If confidence is very low, downgrade to HOLD
        if confidence < 0.2:
            signal = Signal.HOLD

        return StockSignal(
            ticker=ticker,
            signal=signal,
            composite_score=composite,
            confidence=confidence,
            breakdown=breakdown,
            price=price_data.get("price") if price_data else None,
            change_pct=price_data.get("change_pct") if price_data else None,
            top_headlines=top_headlines or [],
            politician_activity=politician_summary,
            timestamp=datetime.now(),
        )

    def _calculate_momentum(self, history: list[dict]) -> float:
        """Calculate price momentum score from -1.0 to +1.0.

        Uses a combination of:
        - Short-term momentum (5-day)
        - Medium-term momentum (20-day)
        - RSI-based overbought/oversold signal
        """
        if not history or len(history) < 5:
            return 0.0

        closes = [d["close"] for d in history]

        # Short-term: 5-day return
        short_ret = 0.0
        if len(closes) >= 5 and closes[-5] != 0:
            short_ret = (closes[-1] - closes[-5]) / closes[-5]

        # Medium-term: 20-day return
        medium_ret = 0.0
        if len(closes) >= 20 and closes[-20] != 0:
            medium_ret = (closes[-1] - closes[-20]) / closes[-20]

        # RSI (14-period)
        rsi = self._calculate_rsi(closes, period=14)
        rsi_signal = 0.0
        if rsi is not None:
            if rsi < 30:
                rsi_signal = 0.5  # Oversold = bullish signal
            elif rsi > 70:
                rsi_signal = -0.5  # Overbought = bearish signal
            else:
                rsi_signal = (50 - rsi) / 100  # Mild signal

        # Combine: weight short-term more
        momentum = (short_ret * 0.4) + (medium_ret * 0.3) + (rsi_signal * 0.3)
        return max(-1.0, min(1.0, momentum))

    @staticmethod
    def _calculate_rsi(prices: list[float], period: int = 14) -> Optional[float]:
        """Calculate RSI (Relative Strength Index)."""
        if len(prices) < period + 1:
            return None

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        recent = deltas[-period:]

        gains = [d for d in recent if d > 0]
        losses = [-d for d in recent if d < 0]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calculate_confidence(
        article_count: int,
        social_count: int,
        politician_trade_count: int,
        price_history: Optional[list[dict]],
    ) -> float:
        """Calculate confidence score (0.0 to 1.0) based on data availability.

        More data sources = higher confidence.
        """
        score = 0.0

        # News (0 - 0.35)
        if article_count > 0:
            score += min(0.35, article_count * 0.035)

        # Social (0 - 0.25)
        if social_count > 0:
            score += min(0.25, social_count * 0.025)

        # Politicians (0 - 0.25)
        if politician_trade_count > 0:
            score += min(0.25, politician_trade_count * 0.05)

        # Price history (0 - 0.15)
        if price_history and len(price_history) >= 20:
            score += 0.15
        elif price_history and len(price_history) >= 5:
            score += 0.10

        return min(1.0, round(score, 2))

    @staticmethod
    def _score_to_signal(score: float) -> Signal:
        """Map a composite score to a buy/sell/hold signal."""
        if score >= STRONG_BUY_THRESHOLD:
            return Signal.STRONG_BUY
        elif score >= BUY_THRESHOLD:
            return Signal.BUY
        elif score <= STRONG_SELL_THRESHOLD:
            return Signal.STRONG_SELL
        elif score <= SELL_THRESHOLD:
            return Signal.SELL
        else:
            return Signal.HOLD
