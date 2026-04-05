"""Rich terminal dashboard for real-time trading signals."""

import logging
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trading_algorithm.signals import Signal, StockSignal

logger = logging.getLogger(__name__)

# Color mapping for signals
SIGNAL_COLORS = {
    Signal.STRONG_BUY: "bold bright_green",
    Signal.BUY: "green",
    Signal.HOLD: "yellow",
    Signal.SELL: "red",
    Signal.STRONG_SELL: "bold bright_red",
}

SIGNAL_ICONS = {
    Signal.STRONG_BUY: "^^ STRONG BUY",
    Signal.BUY: "^  BUY",
    Signal.HOLD: "-- HOLD",
    Signal.SELL: "v  SELL",
    Signal.STRONG_SELL: "vv STRONG SELL",
}


class TradingDashboard:
    """Renders the live trading dashboard in the terminal."""

    def __init__(self):
        self.console = Console()
        self._signals: dict[str, StockSignal] = {}
        self._market_news: list[str] = []
        self._last_update: datetime = datetime.now()
        self._cycle_count: int = 0

    def update(
        self,
        signals: dict[str, StockSignal],
        market_news: list[str] = None,
    ):
        """Update dashboard with new signal data."""
        self._signals = signals
        if market_news:
            self._market_news = market_news[:10]
        self._last_update = datetime.now()
        self._cycle_count += 1

    def render(self) -> Layout:
        """Build the full dashboard layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )

        layout["header"].update(self._render_header())
        layout["body"].split_row(
            Layout(name="signals", ratio=3),
            Layout(name="sidebar", ratio=2),
        )
        layout["body"]["signals"].update(self._render_signal_table())
        layout["body"]["sidebar"].split_column(
            Layout(name="news", ratio=1),
            Layout(name="politicians", ratio=1),
        )
        layout["body"]["sidebar"]["news"].update(self._render_news_panel())
        layout["body"]["sidebar"]["politicians"].update(
            self._render_politician_panel()
        )
        layout["footer"].update(self._render_footer())

        return layout

    def _render_header(self) -> Panel:
        """Render the top header bar."""
        title = Text()
        title.append(" SENTINEL ", style="bold white on blue")
        title.append("  Trading Signal Dashboard  ", style="bold cyan")
        title.append(
            f"  Last update: {self._last_update.strftime('%H:%M:%S')}",
            style="dim white",
        )
        title.append(f"  |  Cycle #{self._cycle_count}", style="dim white")
        return Panel(title, style="blue")

    def _render_signal_table(self) -> Panel:
        """Render the main signal table."""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True,
            title="Live Signals",
        )
        table.add_column("Ticker", style="bold white", width=8)
        table.add_column("Price", justify="right", width=10)
        table.add_column("Chg%", justify="right", width=8)
        table.add_column("Signal", width=16)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Conf", justify="right", width=6)
        table.add_column("News", justify="right", width=6)
        table.add_column("Social", justify="right", width=7)
        table.add_column("Pol.", justify="right", width=6)
        table.add_column("Mom.", justify="right", width=6)

        # Sort by absolute composite score (strongest signals first)
        sorted_signals = sorted(
            self._signals.values(),
            key=lambda s: abs(s.composite_score),
            reverse=True,
        )

        for sig in sorted_signals:
            color = SIGNAL_COLORS.get(sig.signal, "white")
            icon = SIGNAL_ICONS.get(sig.signal, "?")

            price_str = f"${sig.price:.2f}" if sig.price else "N/A"
            change_str = ""
            if sig.change_pct is not None:
                change_color = "green" if sig.change_pct >= 0 else "red"
                change_str = f"[{change_color}]{sig.change_pct:+.2f}%[/]"
            else:
                change_str = "N/A"

            table.add_row(
                sig.ticker,
                price_str,
                change_str,
                f"[{color}]{icon}[/]",
                f"[{color}]{sig.composite_score:+.3f}[/]",
                f"{sig.confidence:.0%}",
                f"{sig.breakdown.news_sentiment_score:+.2f}",
                f"{sig.breakdown.social_sentiment_score:+.2f}",
                f"{sig.breakdown.politician_score:+.2f}",
                f"{sig.breakdown.momentum_score:+.2f}",
            )

        return Panel(table, border_style="cyan")

    def _render_news_panel(self) -> Panel:
        """Render the news headlines sidebar."""
        text = Text()
        if self._signals:
            # Show headlines from the strongest signal
            top_signal = max(
                self._signals.values(),
                key=lambda s: abs(s.composite_score),
                default=None,
            )
            if top_signal and top_signal.top_headlines:
                text.append(f"Top stories for {top_signal.ticker}:\n", style="bold")
                for i, headline in enumerate(top_signal.top_headlines[:5], 1):
                    truncated = headline[:80] + "..." if len(headline) > 80 else headline
                    text.append(f" {i}. {truncated}\n", style="dim")
            else:
                text.append("No recent headlines.", style="dim")

        if self._market_news:
            text.append("\nMarket News:\n", style="bold")
            for i, headline in enumerate(self._market_news[:5], 1):
                truncated = headline[:80] + "..." if len(headline) > 80 else headline
                text.append(f" {i}. {truncated}\n", style="dim")

        return Panel(text, title="Headlines", border_style="green")

    def _render_politician_panel(self) -> Panel:
        """Render politician trading activity sidebar."""
        text = Text()
        has_activity = False

        for sig in self._signals.values():
            if sig.politician_activity:
                has_activity = True
                text.append(f"{sig.ticker}: ", style="bold")
                text.append(f"{sig.politician_activity}\n", style="dim")

        if not has_activity:
            text.append("No recent politician trades detected.", style="dim")

        return Panel(text, title="Politician Activity", border_style="magenta")

    def _render_footer(self) -> Panel:
        """Render the bottom status bar."""
        buy_count = sum(
            1
            for s in self._signals.values()
            if s.signal in (Signal.BUY, Signal.STRONG_BUY)
        )
        sell_count = sum(
            1
            for s in self._signals.values()
            if s.signal in (Signal.SELL, Signal.STRONG_SELL)
        )
        hold_count = sum(
            1 for s in self._signals.values() if s.signal == Signal.HOLD
        )

        footer = Text()
        footer.append(" Summary: ", style="bold")
        footer.append(f" {buy_count} BUY ", style="bold green")
        footer.append("|")
        footer.append(f" {hold_count} HOLD ", style="bold yellow")
        footer.append("|")
        footer.append(f" {sell_count} SELL ", style="bold red")
        footer.append(
            f"   |   Tracking {len(self._signals)} stocks   |   "
            f"Press Ctrl+C to exit",
            style="dim",
        )
        return Panel(footer, style="blue")

    def create_live_context(self, refresh_per_second: int = 2) -> Live:
        """Create a Rich Live context for continuous updates."""
        return Live(
            self.render(),
            console=self.console,
            refresh_per_second=refresh_per_second,
            screen=True,
        )
