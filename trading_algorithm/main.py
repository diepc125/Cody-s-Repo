#!/usr/bin/env python3
"""Main entry point — orchestrates all components and runs the live dashboard."""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime

from trading_algorithm.config import POLL_INTERVAL_SECONDS, WATCHED_STOCKS
from trading_algorithm.dashboard import TradingDashboard
from trading_algorithm.data_fetcher import NewsFetcher, StockDataFetcher
from trading_algorithm.political_tracker import PoliticalTradeTracker
from trading_algorithm.sentiment import SentimentAnalyzer, SentimentTracker
from trading_algorithm.signals import SignalGenerator, StockSignal

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("trading_algorithm.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TradingEngine:
    """Core engine that ties all components together."""

    def __init__(self, tickers: list[str]):
        self.tickers = tickers
        self.stock_fetcher = StockDataFetcher(tickers)
        self.news_fetcher = NewsFetcher()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.sentiment_tracker = SentimentTracker()
        self.political_tracker = PoliticalTradeTracker()
        self.signal_generator = SignalGenerator()
        self.dashboard = TradingDashboard()
        self._running = False

    def run_cycle(self) -> dict[str, StockSignal]:
        """Execute one full data-fetch + analysis + signal cycle."""
        signals = {}

        # 1. Fetch live stock prices
        quotes = self.stock_fetcher.fetch_live_quotes()

        # 2. Fetch politician signals (cached, refreshes every 15 min)
        politician_signals = self.political_tracker.get_all_signals(self.tickers)

        # 3. Fetch general market news
        market_news = self.news_fetcher.fetch_general_market_news(max_articles=15)
        market_headlines = [a["title"] for a in market_news]

        # 4. Per-ticker analysis
        for ticker in self.tickers:
            try:
                # News sentiment
                articles = self.news_fetcher.fetch_ticker_news(ticker, max_articles=15)
                news_sentiment = self.sentiment_analyzer.analyze_articles(articles)
                news_sentiment.ticker = ticker

                # Track sentiment history
                self.sentiment_tracker.update(ticker, news_sentiment)

                # Politician signal
                pol_signal = politician_signals.get(ticker)
                pol_score = pol_signal.signal_score if pol_signal else 0.0
                pol_trade_count = (
                    (pol_signal.buy_count + pol_signal.sell_count) if pol_signal else 0
                )
                pol_summary = ""
                if pol_signal and pol_trade_count > 0:
                    pol_summary = (
                        f"{pol_signal.buy_count} buys, {pol_signal.sell_count} sells "
                        f"by {', '.join(pol_signal.notable_traders[:3])}"
                    )

                # Price history for momentum
                price_history = self.stock_fetcher.fetch_price_history(ticker, days=30)

                # Generate composite signal
                stock_signal = self.signal_generator.generate_signal(
                    ticker=ticker,
                    news_score=news_sentiment.news_score,
                    social_score=news_sentiment.social_score,  # TODO: add real social source
                    politician_score=pol_score,
                    price_data=quotes.get(ticker),
                    price_history=price_history,
                    article_count=news_sentiment.article_count,
                    social_count=news_sentiment.social_mention_count,
                    politician_trade_count=pol_trade_count,
                    top_headlines=news_sentiment.top_headlines,
                    politician_summary=pol_summary,
                )
                signals[ticker] = stock_signal

            except Exception as exc:
                logger.error("Error processing %s: %s", ticker, exc)

        # Update dashboard
        self.dashboard.update(signals, market_news=market_headlines)
        return signals

    def run_live(self):
        """Run the live trading dashboard with continuous polling."""
        self._running = True

        def handle_shutdown(signum, frame):
            self._running = False
            print("\nShutting down gracefully...")

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        print("Starting Sentinel Trading Dashboard...")
        print(f"Tracking {len(self.tickers)} stocks: {', '.join(self.tickers)}")
        print(f"Polling every {POLL_INTERVAL_SECONDS} seconds")
        print("Press Ctrl+C to stop\n")

        # Initial data fetch before starting live display
        print("Fetching initial data...")
        self.run_cycle()

        with self.dashboard.create_live_context(refresh_per_second=1) as live:
            while self._running:
                try:
                    self.run_cycle()
                    live.update(self.dashboard.render())
                    time.sleep(POLL_INTERVAL_SECONDS)
                except KeyboardInterrupt:
                    break
                except Exception as exc:
                    logger.error("Cycle error: %s", exc)
                    time.sleep(POLL_INTERVAL_SECONDS)

        print("\nDashboard stopped. Final signals saved to trading_algorithm.log")

    def run_once(self):
        """Run a single analysis cycle and print results to stdout."""
        signals = self.run_cycle()

        print(f"\n{'='*80}")
        print(f" SENTINEL TRADING SIGNALS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")

        # Sort by strength
        sorted_signals = sorted(
            signals.values(), key=lambda s: abs(s.composite_score), reverse=True
        )

        for sig in sorted_signals:
            price_str = f"${sig.price:.2f}" if sig.price else "N/A"
            change_str = f"{sig.change_pct:+.2f}%" if sig.change_pct is not None else ""
            print(
                f"  {sig.ticker:<6} {price_str:>10} {change_str:>8}  "
                f"=> {sig.signal.value:<14} "
                f"(score: {sig.composite_score:+.3f}, conf: {sig.confidence:.0%})"
            )
            if sig.politician_activity:
                print(f"         Politicians: {sig.politician_activity}")
            if sig.top_headlines:
                print(f"         Top headline: {sig.top_headlines[0][:70]}...")
            print()

        print(f"{'='*80}")
        buy_count = sum(1 for s in signals.values() if "BUY" in s.signal.value)
        sell_count = sum(1 for s in signals.values() if "SELL" in s.signal.value)
        hold_count = sum(1 for s in signals.values() if s.signal.value == "HOLD")
        print(f" Summary: {buy_count} BUY | {hold_count} HOLD | {sell_count} SELL")
        print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Sentinel — Sentiment-driven stock trading signal generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m trading_algorithm.main --live
  python -m trading_algorithm.main --once
  python -m trading_algorithm.main --tickers AAPL TSLA NVDA --live
  python -m trading_algorithm.main --interval 10 --live
        """,
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run the live dashboard with continuous polling (default)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single analysis cycle and exit",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=WATCHED_STOCKS,
        help="Stock tickers to track (default: predefined list)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=POLL_INTERVAL_SECONDS,
        help=f"Polling interval in seconds (default: {POLL_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Logging level (default: WARNING)",
    )

    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Override polling interval if specified
    if args.interval != POLL_INTERVAL_SECONDS:
        import trading_algorithm.config as cfg
        cfg.POLL_INTERVAL_SECONDS = args.interval

    engine = TradingEngine(tickers=args.tickers)

    if args.once:
        engine.run_once()
    else:
        engine.run_live()


if __name__ == "__main__":
    main()
