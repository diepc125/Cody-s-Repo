# Sentinel — Sentiment-Driven Trading Signal Generator

A real-time trading signal system that combines **news sentiment analysis**, **politician trade tracking**, and **price momentum** to generate actionable buy/sell/hold signals.

## Features

- **Live Stock Data** — Pulls real-time prices from Yahoo Finance every 5 seconds
- **News Sentiment Analysis** — Scrapes RSS feeds (Yahoo Finance, MarketWatch, CNBC, Reuters) and scores headlines using VADER sentiment analysis with financial-domain boosters
- **Politician Trade Tracking** — Monitors stock trades by Congress members (Pelosi, Trump, Tuberville, etc.) via Capitol Trades scraping
- **Composite Signal Engine** — Weighted algorithm combining news sentiment (35%), social sentiment (25%), politician activity (25%), and price momentum (15%)
- **Rich Terminal Dashboard** — Live-updating terminal UI showing signals, headlines, and politician activity
- **RSI + Momentum** — Technical indicators (14-period RSI, 5/20-day momentum) feed into the signal

## Architecture

```
trading_algorithm/
├── config.py             # Tracked stocks, politicians, thresholds, weights
├── data_fetcher.py       # Yahoo Finance quotes + RSS news fetcher
├── sentiment.py          # VADER sentiment engine with financial boosters
├── political_tracker.py  # Capitol Trades scraper for politician trades
├── signals.py            # Composite signal generator (buy/sell/hold)
├── dashboard.py          # Rich terminal dashboard
└── main.py               # Entry point and orchestration engine
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Live dashboard (continuous polling every 5 seconds)
python -m trading_algorithm.main --live

# Single analysis pass (print and exit)
python -m trading_algorithm.main --once

# Track specific tickers
python -m trading_algorithm.main --tickers AAPL TSLA NVDA --live

# Custom polling interval (10 seconds)
python -m trading_algorithm.main --interval 10 --live

# Verbose logging
python -m trading_algorithm.main --live --log-level DEBUG
```

## Signal Scale

| Signal       | Composite Score | Meaning                          |
|-------------|-----------------|----------------------------------|
| STRONG BUY  | >= +0.35        | Strong bullish sentiment across sources |
| BUY         | >= +0.15        | Moderately bullish                |
| HOLD        | -0.15 to +0.15  | Neutral / mixed signals           |
| SELL         | <= -0.15        | Moderately bearish                |
| STRONG SELL | <= -0.35        | Strong bearish sentiment across sources |

## Disclaimer

This tool is for **educational and research purposes only**. It is not financial advice. Always do your own research before making investment decisions.
