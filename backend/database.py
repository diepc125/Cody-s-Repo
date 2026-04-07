"""Sentinel database — SQLite persistence for signal and sentiment history.

All SQL lives here. Nothing outside this module should execute queries.
Schema versioning is handled via PRAGMA user_version; add a new migration
block for each schema change and increment _SCHEMA_VERSION.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sentinel.db"
_SCHEMA_VERSION = 1


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and apply pending migrations. Safe to call on every startup."""
    with _connect() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]

        if version < 1:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS signal_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker          TEXT    NOT NULL,
                    ts              INTEGER NOT NULL,
                    signal          TEXT    NOT NULL,
                    score           REAL    NOT NULL,
                    confidence      REAL    NOT NULL,
                    news_score      REAL    NOT NULL,
                    social_score    REAL    NOT NULL,
                    political_score REAL    NOT NULL,
                    momentum_score  REAL    NOT NULL,
                    cvi_label       TEXT    NOT NULL DEFAULT '',
                    insider_score   REAL    NOT NULL DEFAULT 0.0,
                    crowd_score     REAL    NOT NULL DEFAULT 0.0,
                    price           REAL,
                    change_pct      REAL
                );
                CREATE INDEX IF NOT EXISTS idx_sh_ticker_ts
                    ON signal_history (ticker, ts);
                PRAGMA user_version = 1;
            """)


# ── Writes ────────────────────────────────────────────────────────────────────

def save_signals(signals: dict[str, dict]) -> None:
    """Persist one poll cycle's worth of signals to the database."""
    now = int(datetime.now().timestamp())
    rows = [
        (
            ticker,
            now,
            s["signal"],
            s["score"],
            s["confidence"],
            s["breakdown"]["news"],
            s["breakdown"]["social"],
            s["breakdown"]["political"],
            s["breakdown"]["momentum"],
            s.get("crowd_vs_insiders", {}).get("label", ""),
            s.get("crowd_vs_insiders", {}).get("insider_score", 0.0),
            s.get("crowd_vs_insiders", {}).get("crowd_score", 0.0),
            s.get("price"),
            s.get("change_pct"),
        )
        for ticker, s in signals.items()
    ]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO signal_history
                (ticker, ts, signal, score, confidence,
                 news_score, social_score, political_score, momentum_score,
                 cvi_label, insider_score, crowd_score, price, change_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )


# ── Reads ─────────────────────────────────────────────────────────────────────

def get_signal_history(ticker: str, days: int = 30) -> list[dict]:
    """Return signal rows for a ticker over the last N days, oldest first."""
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT ts, signal, score, confidence,
                   news_score, social_score, political_score, momentum_score,
                   cvi_label, insider_score, crowd_score, price, change_pct
            FROM   signal_history
            WHERE  ticker = ? AND ts >= ?
            ORDER  BY ts ASC
            """,
            (ticker.upper(), since),
        ).fetchall()
    return [dict(r) for r in rows]


def get_sentiment_history(ticker: str) -> list[dict]:
    """Return time-series of news + composite scores for the sentiment chart.

    Composite is recomputed from stored component scores using the same
    weights as the signal generator so the chart stays consistent.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT ts,
                   news_score AS score,
                   (news_score        * 0.35
                    + social_score    * 0.25
                    + political_score * 0.25
                    + momentum_score  * 0.15) AS combined
            FROM   signal_history
            WHERE  ticker = ?
            ORDER  BY ts ASC
            """,
            (ticker.upper(),),
        ).fetchall()
    return [{"time": r["ts"], "score": r["score"], "combined": r["combined"]} for r in rows]
