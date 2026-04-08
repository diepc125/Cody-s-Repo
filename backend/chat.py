"""Sentinel chat engine — local LLM reasoning over app state.

Talks to a local Ollama instance via its OpenAI-compatible API at
http://localhost:11434/v1. The model is given a handful of tools that
read directly from the running AppState (and the SQLite signal history)
so it can ground every answer in Sentinel's real data instead of
inventing prices or headlines.

Defaults to Qwen 2.5 14B Instruct (Q5_K_M), which fits comfortably
alongside FinBERT on a 16GB GPU and has strong native tool-calling.
Override via the SENTINEL_CHAT_MODEL environment variable.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

import database

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("SENTINEL_CHAT_BASE_URL", "http://localhost:11434/v1")
_MODEL    = os.environ.get("SENTINEL_CHAT_MODEL", "qwen2.5:14b-instruct-q5_K_M")

_SYSTEM_PROMPT = """You are Sentinel, an AI assistant embedded in a stock-signals dashboard.

You help the user interpret the dashboard's data. You have tools that return
the current signals, ticker details, historical signals, and recent news for
the user's tracked watchlist. ALWAYS call a tool before making any claim about
a specific ticker — never guess prices, scores, or headlines.

When you answer, cite which data you used (e.g. "based on the current signal
for NVDA" or "based on today's headlines"). Be concise and direct.

How the composite score works:
  Range is -1 (bearish) to +1 (bullish).
  Thresholds: +/-0.15 = HOLD zone, +/-0.35 = STRONG.
  Weights: News 30%, Social 20%, Political 20%, Momentum 10%, Quant 20%.

When the user asks "what should I buy":
  1. Call get_all_signals.
  2. Rank by (score * confidence) and pick the top 2-3 that are BUY or STRONG BUY.
  3. For each pick, call get_ticker_detail to explain the breakdown.
  4. Note any crowd-vs-insiders label worth flagging.

Stay within the tracked watchlist. If asked about a ticker Sentinel doesn't
track, say so politely and list the tickers that are tracked.

Always end any response that recommends an action with:
"Not financial advice — this is signal analysis for research only."
"""

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_all_signals",
            "description": (
                "Return the current signal, composite score, confidence, price, "
                "and day change for every tracked ticker. Call this first for "
                "any broad question like 'what should I buy' or 'what's strong "
                "today'."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticker_detail",
            "description": (
                "Return the full breakdown for one ticker: signal, composite "
                "score, confidence, news/social/political/momentum/quant "
                "sub-scores, crowd-vs-insiders label, quant indicators, and "
                "top recent headlines."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Ticker symbol, e.g. NVDA",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_signal_history",
            "description": (
                "Return the historical signal rows for a ticker over the last "
                "N days from the SQLite database. Useful for 'why did X drop' "
                "or 'how has Y been trending this week'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "days": {
                        "type": "integer",
                        "description": "Lookback window in days (1-365)",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_news",
            "description": (
                "Return the most recent news headlines for a ticker. Use this "
                "to explain sentiment moves or answer 'any news on X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "description": "Max headlines to return (1-10)",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
]


class ChatEngine:
    """Wraps a local Ollama LLM with Sentinel-specific tools."""

    def __init__(self, state: Any):
        self.state = state
        self.client = OpenAI(base_url=_BASE_URL, api_key="ollama")

    # ── Tool implementations ──────────────────────────────────────────
    def _tool_get_all_signals(self) -> list[dict]:
        return [
            {
                "ticker": t,
                "signal": s["signal"],
                "score": round(s["score"], 3),
                "confidence": round(s["confidence"], 3),
                "price": s.get("price"),
                "change_pct": s.get("change_pct"),
            }
            for t, s in self.state.latest_signals.items()
        ]

    def _tool_get_ticker_detail(self, ticker: str) -> dict:
        sig = self.state.latest_signals.get(ticker.upper())
        if not sig:
            tracked = sorted(self.state.latest_signals.keys())
            return {
                "error": f"{ticker.upper()} is not tracked by Sentinel",
                "tracked_tickers": tracked,
            }
        return {
            "ticker": sig["ticker"],
            "signal": sig["signal"],
            "score": round(sig["score"], 3),
            "confidence": round(sig["confidence"], 3),
            "price": sig.get("price"),
            "change_pct": sig.get("change_pct"),
            "breakdown": sig.get("breakdown", {}),
            "quant": sig.get("quant", {}),
            "crowd_vs_insiders": sig.get("crowd_vs_insiders", {}),
            "top_headlines": sig.get("headlines", [])[:5],
            "politician_activity": sig.get("politician_activity", ""),
        }

    def _tool_get_signal_history(self, ticker: str, days: int = 14) -> list[dict]:
        days = max(1, min(int(days), 365))
        rows = database.get_signal_history(ticker.upper(), days)
        # Cap payload so the model's context stays manageable
        return rows[-40:]

    def _tool_get_recent_news(self, ticker: str, limit: int = 5) -> list[dict]:
        limit = max(1, min(int(limit), 10))
        try:
            articles = self.state.news_fetcher.fetch_ticker_news(
                ticker.upper(), max_articles=limit
            )
        except Exception as exc:
            return [{"error": f"news fetch failed: {exc}"}]
        return [
            {
                "title": a.get("title", ""),
                "source": a.get("source", ""),
                "published": a["published"].isoformat()
                if hasattr(a.get("published"), "isoformat")
                else str(a.get("published", "")),
            }
            for a in articles
        ]

    def _dispatch(self, name: str, args: dict) -> Any:
        try:
            if name == "get_all_signals":
                return self._tool_get_all_signals()
            if name == "get_ticker_detail":
                return self._tool_get_ticker_detail(args["ticker"])
            if name == "get_signal_history":
                return self._tool_get_signal_history(
                    args["ticker"], args.get("days", 14)
                )
            if name == "get_recent_news":
                return self._tool_get_recent_news(
                    args["ticker"], args.get("limit", 5)
                )
            return {"error": f"unknown tool: {name}"}
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return {"error": str(exc)}

    # ── Main entry point ──────────────────────────────────────────────
    def chat(self, messages: list[dict], max_tool_rounds: int = 5) -> dict:
        """Run one chat turn.

        `messages` is a list of {role, content} dicts from the UI.
        Returns {reply, tools_used, model} — tools_used is a flat trace of
        every tool the model invoked, so the UI can surface what it looked at.
        """
        convo: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        convo.extend(messages)
        tools_used: list[dict] = []

        for _ in range(max_tool_rounds):
            try:
                resp = self.client.chat.completions.create(
                    model=_MODEL,
                    messages=convo,
                    tools=_TOOLS,
                    temperature=0.3,
                )
            except Exception as exc:
                logger.exception("Ollama call failed")
                return {
                    "reply": (
                        f"Couldn't reach the local LLM: {exc}. "
                        f"Is Ollama running at {_BASE_URL}?"
                    ),
                    "tools_used": tools_used,
                    "model": _MODEL,
                }

            msg = resp.choices[0].message
            convo.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                return {
                    "reply": msg.content or "",
                    "tools_used": tools_used,
                    "model": _MODEL,
                }

            for call in msg.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._dispatch(name, args)
                tools_used.append({"name": name, "args": args})
                payload = json.dumps(result, default=str)
                if len(payload) > 8000:
                    payload = payload[:8000] + '..."_truncated":true}'
                convo.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": payload,
                    }
                )

        return {
            "reply": (
                "I kept calling tools without reaching a final answer — "
                "try rephrasing your question more specifically."
            ),
            "tools_used": tools_used,
            "model": _MODEL,
        }
