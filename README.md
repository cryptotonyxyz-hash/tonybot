# TonyBot — Crypto Trading Signal System

A Python bot that watches crypto futures markets 24/7, detects setups using a
regime-switching strategy, and pushes trade signals straight to Telegram. It's
a **signal service, not an auto-execution bot** — the user always makes the
final call on whether to take a trade.

## How it works

TonyBot scans a fixed watchlist of major pairs (BTC, ETH, SOL, XRP, DOGE, ADA,
DOT, SUI, TON) on the 1-hour timeframe and switches between two strategies
depending on market conditions, measured by ADX (Average Directional Index):

- **Bounce strategy** (choppy market, ADX < 30) — looks for price tagging the
  outer Bollinger Bands with RSI confirmation, betting on mean reversion back
  toward the middle of the range.
- **Trend strategy** (trending market, ADX ≥ 30) — looks for price holding
  above/below the 50 EMA with RSI in a healthy (non-exhausted) range, betting
  on continuation.

Every signal gets a dynamic stop-loss and take-profit calculated from ATR
(Average True Range), so risk sizing adapts to each coin's actual volatility
instead of using a fixed percentage.

### Extra filters
- **Whale radar** — scans recent trades for single orders over $500k and uses
  the imbalance between whale buying and selling to confirm or veto a signal
  (e.g. it won't fire a SHORT if whales are aggressively buying).
- **Cooldowns** — after a trade closes, that pair goes on a cooldown timer
  (30 min after a win, 1 hour after a loss) to avoid immediately re-entering
  a level that just got tested.
- **Trade persistence** — open positions are saved to `trades.json` so state
  survives a restart, and a summary of open positions with live P&L is sent
  to Telegram every 4 hours.

## Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your own Telegram bot token and
   chat ID:
   ```bash
   cp .env.example .env
   ```
3. Run it:
   ```bash
   python bot.py
   ```

## Disclaimer

This project is for educational and informational purposes. It is a signal
generator, not financial advice, and does not execute trades on your behalf.
Crypto trading carries significant risk — always do your own research.
