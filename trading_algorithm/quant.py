"""Quantitative analysis — mathematical models for identifying trade opportunities.

Four independent indicators are computed from daily OHLCV history:

  1. Z-Score Mean Reversion  — how far price has deviated from its 20-day mean
  2. MACD                    — 12/26 EMA convergence/divergence vs 9-period signal line
  3. OBV Trend               — On-Balance Volume direction (volume confirms price moves)
  4. Bollinger %B            — price position within 2-std Bollinger Bands

Each indicator returns a score in [-1, +1].  Positive = bullish, negative = bearish.
The composite quant_score is an equal-weight average of all four.
"""

import logging
import statistics
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_CLAMP = lambda v: max(-1.0, min(1.0, v))


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class QuantSignal:
    name: str           # "MACD", "Mean Reversion", etc.
    verdict: str        # human-readable: "Bullish Cross", "Oversold", …
    score: float        # -1 to +1
    value: float        # raw indicator value for display (z-score, %B, etc.)
    bullish: bool       # True = bullish, False = bearish/neutral


@dataclass
class QuantResult:
    score: float                          # composite -1 to +1
    signals: list[QuantSignal] = field(default_factory=list)
    zscore: float = 0.0
    macd_histogram: float = 0.0
    pct_b: float = 0.5
    obv_slope: float = 0.0


# ── EMA helper ────────────────────────────────────────────────────────────────

def _ema(values: list[float], period: int) -> list[float]:
    """Return EMA series for the given period.  Returns [] if insufficient data."""
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


# ── Individual indicators ─────────────────────────────────────────────────────

def _zscore_mean_reversion(closes: list[float]) -> QuantSignal:
    """Z-score of current price vs. 20-day rolling mean.

    A large negative z-score means price is unusually low → mean-reversion buy.
    A large positive z-score means price is unusually high → mean-reversion sell.
    """
    if len(closes) < 20:
        return QuantSignal("Mean Reversion", "Insufficient data", 0.0, 0.0, False)

    window = closes[-20:]
    mean = statistics.mean(window)
    try:
        std = statistics.stdev(window)
    except statistics.StatisticsError:
        std = 0.0

    if std == 0:
        return QuantSignal("Mean Reversion", "No volatility", 0.0, 0.0, False)

    z = (closes[-1] - mean) / std

    # Map z-score to [-1, +1]: z of -3 → score +1 (very oversold), z of +3 → -1
    score = _CLAMP(-z / 2.5)

    if z <= -2.0:
        verdict = f"Strongly Oversold (z={z:.2f})"
        bullish = True
    elif z <= -1.0:
        verdict = f"Oversold (z={z:.2f})"
        bullish = True
    elif z >= 2.0:
        verdict = f"Strongly Overbought (z={z:.2f})"
        bullish = False
    elif z >= 1.0:
        verdict = f"Overbought (z={z:.2f})"
        bullish = False
    else:
        verdict = f"Near Mean (z={z:.2f})"
        bullish = score >= 0

    return QuantSignal("Mean Reversion", verdict, round(score, 4), round(z, 3), bullish)


def _macd(closes: list[float]) -> QuantSignal:
    """MACD (12, 26, 9) — measures momentum via EMA convergence/divergence.

    Histogram = MACD line − signal line.
    Positive histogram → bullish momentum; negative → bearish.
    A recent sign change (cross) is a stronger signal.
    """
    if len(closes) < 27:
        return QuantSignal("MACD", "Insufficient data", 0.0, 0.0, False)

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)

    # Align the two EMA series
    offset = len(ema12) - len(ema26)
    macd_line = [a - b for a, b in zip(ema12[offset:], ema26)]

    signal_line = _ema(macd_line, 9)
    if not signal_line:
        return QuantSignal("MACD", "Insufficient data", 0.0, 0.0, False)

    # Align macd_line to signal_line length
    hist_offset = len(macd_line) - len(signal_line)
    histogram = [m - s for m, s in zip(macd_line[hist_offset:], signal_line)]

    current_hist = histogram[-1]
    prev_hist = histogram[-2] if len(histogram) >= 2 else 0.0

    # Detect cross (sign change in histogram)
    crossed_bullish = prev_hist < 0 < current_hist
    crossed_bearish = prev_hist > 0 > current_hist

    # Normalize histogram by recent price to get a scale-independent score
    ref_price = closes[-1] or 1.0
    norm = current_hist / ref_price  # typically very small, ±0.005
    score = _CLAMP(norm * 200)       # scale to ±1 range

    if crossed_bullish:
        verdict = "Bullish Cross"
        bullish = True
        score = max(score, 0.4)     # boost on fresh cross
    elif crossed_bearish:
        verdict = "Bearish Cross"
        bullish = False
        score = min(score, -0.4)
    elif current_hist > 0:
        verdict = "Above Signal"
        bullish = True
    else:
        verdict = "Below Signal"
        bullish = False

    return QuantSignal("MACD", verdict, round(score, 4), round(current_hist, 4), bullish)


def _obv_trend(closes: list[float], volumes: list[float]) -> QuantSignal:
    """On-Balance Volume — accumulates volume on up days, subtracts on down days.

    Compares short-term OBV trend (5-day slope) to longer-term (20-day).
    Rising OBV with price = institutional accumulation → bullish.
    Falling OBV with rising price = distribution → bearish divergence.
    """
    if len(closes) < 6 or len(volumes) < 6:
        return QuantSignal("OBV Trend", "Insufficient data", 0.0, 0.0, False)

    n = min(len(closes), len(volumes))
    closes = closes[-n:]
    volumes = volumes[-n:]

    # Build OBV series
    obv = [0.0]
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])

    # 5-day slope (recent trend)
    short_slope = obv[-1] - obv[-5]
    # 20-day slope (context) — only if we have enough data
    long_slope = (obv[-1] - obv[-20]) if len(obv) >= 20 else short_slope

    # Normalize by average volume so the number is scale-independent
    avg_vol = statistics.mean(volumes) or 1.0
    norm_short = short_slope / avg_vol / 5    # per-day fraction
    norm_long = long_slope / avg_vol / max(20, n)

    # Score: weight recent slope more
    raw = (norm_short * 0.7) + (norm_long * 0.3)
    score = _CLAMP(raw * 3)

    if norm_short > 0.1:
        verdict = "Strong Accumulation"
        bullish = True
    elif norm_short > 0:
        verdict = "Mild Accumulation"
        bullish = True
    elif norm_short < -0.1:
        verdict = "Strong Distribution"
        bullish = False
    else:
        verdict = "Mild Distribution"
        bullish = False

    return QuantSignal("OBV Trend", verdict, round(score, 4), round(norm_short, 4), bullish)


def _bollinger_pct_b(closes: list[float]) -> QuantSignal:
    """Bollinger %B — where the current price sits within the bands.

    %B = 0   → at lower band (oversold context)
    %B = 0.5 → at middle (20-day mean)
    %B = 1   → at upper band (overbought context)
    %B < 0 or > 1 → outside the bands (extreme move)
    """
    if len(closes) < 20:
        return QuantSignal("Bollinger %B", "Insufficient data", 0.0, 0.5, False)

    window = closes[-20:]
    mean = statistics.mean(window)
    try:
        std = statistics.stdev(window)
    except statistics.StatisticsError:
        std = 0.0

    if std == 0:
        return QuantSignal("Bollinger %B", "No volatility", 0.0, 0.5, False)

    upper = mean + 2 * std
    lower = mean - 2 * std
    band_width = upper - lower

    pct_b = (closes[-1] - lower) / band_width if band_width > 0 else 0.5

    # Map to score: %B near 0 → +1 (oversold), near 1 → -1 (overbought)
    score = _CLAMP(1 - 2 * pct_b)

    if pct_b < 0:
        verdict = f"Below Lower Band (%B={pct_b:.2f})"
        bullish = True
    elif pct_b < 0.2:
        verdict = f"Near Lower Band (%B={pct_b:.2f})"
        bullish = True
    elif pct_b > 1:
        verdict = f"Above Upper Band (%B={pct_b:.2f})"
        bullish = False
    elif pct_b > 0.8:
        verdict = f"Near Upper Band (%B={pct_b:.2f})"
        bullish = False
    else:
        verdict = f"Mid-Band (%B={pct_b:.2f})"
        bullish = score >= 0

    return QuantSignal("Bollinger %B", verdict, round(score, 4), round(pct_b, 3), bullish)


# ── Public API ────────────────────────────────────────────────────────────────

class QuantAnalyzer:
    """Runs all quant indicators and returns a composite score + per-indicator breakdown."""

    def analyze(self, history: list[dict]) -> QuantResult:
        """Compute quant signals from daily OHLCV history.

        Args:
            history: List of dicts with keys: open, high, low, close, volume.
                     Must be in chronological order (oldest first).

        Returns:
            QuantResult with composite score in [-1, +1] and individual signals.
        """
        if not history or len(history) < 5:
            return QuantResult(score=0.0)

        closes  = [d["close"]  for d in history]
        volumes = [float(d.get("volume") or 0) for d in history]

        zscore_sig = _zscore_mean_reversion(closes)
        macd_sig   = _macd(closes)
        obv_sig    = _obv_trend(closes, volumes)
        bb_sig     = _bollinger_pct_b(closes)

        indicators = [zscore_sig, macd_sig, obv_sig, bb_sig]
        valid = [s for s in indicators if s.verdict != "Insufficient data"]

        if not valid:
            return QuantResult(score=0.0, signals=indicators)

        composite = sum(s.score for s in valid) / len(valid)
        composite = _CLAMP(round(composite, 4))

        return QuantResult(
            score=composite,
            signals=indicators,
            zscore=zscore_sig.value,
            macd_histogram=macd_sig.value,
            pct_b=bb_sig.value,
            obv_slope=obv_sig.value,
        )

    def to_dict(self, result: QuantResult) -> dict:
        return {
            "score": result.score,
            "zscore": result.zscore,
            "macd_histogram": result.macd_histogram,
            "pct_b": result.pct_b,
            "obv_slope": result.obv_slope,
            "signals": [
                {
                    "name": s.name,
                    "verdict": s.verdict,
                    "score": s.score,
                    "value": s.value,
                    "bullish": s.bullish,
                }
                for s in result.signals
            ],
        }
