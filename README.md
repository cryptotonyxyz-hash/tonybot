# TonyBot V3.0 "Jarvis" — Working Rebuild

A rebuild of the original TonyBot V3.0 signal bot, recovered from Gemini's
reconstruction of the original `bot.py`, corrected against two Telegram
screenshots from the live channel and the author's GitHub rewrite
(`cryptotonyxyz-hash/tonybot`).

## Current version (adopted Nov 11, 2026): V3.2 — ATR regime

**`bot_v3_2.py` is the adopted current version.** It is V3.1 (regime
filter, ADX rising, top-6 pairs, trailing stop to breakeven at +0.8R,
12h post-loss cooldown, rebuilt PREMIUM label) with the 50DMA regime
filter REPLACED by a BTC daily ATR(14) percentile band [0.20, 0.80]
— only trade when volatility is in the normal range. SL 1.25x ATR(4h)
and R:R 1:1.8 unchanged. Backtest on the 1,015 matched channel trades:
**138 trades, 52.9% win, +0.560 R/trade, ~+7.0 R/month** (vs V3.1:
183 trades, 45.9% win, +0.411 R; vs V3.0: 42.2% win, +0.018 R).
Equity from $1,000 (bot's own per-trade risk, compounding, as of
09:00 WAT 11 Nov 2026): V3.0 $1,063.49, V3.1 $3,387.60,
V3.2 $3,769.99 — see `channel-analysis/equity-1000usd.txt`.
**Tested and REJECTED, both OFF by default:** the funding-rate filter
(premise backwards — extreme-funding trades are the best; OI history
unobtainable) and partial take-profits (win rate up, expectancy down,
no out-of-sample lift). Flags in `bot_v3_2.py`: `V32_ATR_REGIME=True`,
`V32_USE_50DMA=False`, `V32_FUNDING_FILTER=False`,
`V32_PARTIAL_TP_R=0.0`. Tests: `test_v3_2.py` 16 passed,
`test_v3_1.py` 21 passed. `bot.py` (V3.0 reproduction) is untouched.
Full analysis: `PERFORMANCE.md`. Do NOT deploy with real money on a
backtest alone — forward-test live first. Nothing pushed to GitHub
without Anthony's explicit approval.

## Files

| File | What it is |
|---|---|
| `bot.py` | The working V3.0 rebuild. Signal alerts only, no auto-trading. |
| `bot_v3_1.py` | V3.1: 50DMA regime filter, ADX rising, top-6, trailing BE, 12h cooldown, rebuilt PREMIUM label. |
| `bot_v3_2.py` | **V3.2 (current):** ATR-percentile regime [0.20, 0.80] replacing the 50DMA; funding filter and partial take-profits OFF (tested, rejected). |
| `bot_reconstructed_gemini.py` | Gemini's verbatim reconstruction. Reference only, not runnable (hardcoded indicator values). |
| `test_bot.py` | Tests: indicators, entry logic, stats/reports, live MEXC data. |
| `test_v3_1.py` | V3.1 tests (21, all passing). |
| `test_v3_2.py` | V3.2 tests (16, all passing). |
| `backtest_improvements.py` | V3.1 backtest against the 1,015 matched channel trades. |
| `backtest_v3_2.py` | V3.2 backtest (funding, partial TPs, ATR regime). |
| `equity_1000usd.py` | Equity curves from $1,000 for V3.0/V3.1/V3.2 (bot's own per-trade risk, compounding). Output: `channel-analysis/equity-1000usd.txt`. |
| `parse_channel_export.py` | Parses a Telegram Desktop JSON export of the signal channel into signals, outcomes, formula checks, and a stats seed. See below. |
| `requirements.txt` | `ccxt`, `pandas`, `pandas_ta`, `requests`, `python-dotenv`. |
| `.env.example` | Copy to `.env`, fill in your Telegram token and chat ID. |

## What the bot does

- Scans 15 pairs on MEXC every 60s (4H + 15M candles).
- **Trend signals only** (bounce disabled, as in the original).
- **LONG** only when 4H BULLISH (price >= EMA50 4H) **and** 15M BULLISH
  (price >= EMA50 15M) **and** ADX >= 25. **SHORT** mirrored.
- SL = entry +/- 1.25 * ATR(4H). TP = SL distance * 1.8 (R:R 1:1.8).
- Skips a signal if the stop distance is more than 2.0% of the price
  (account-risk filter). Observed: 1.53% fired; 2.13% and 2.56% skipped.
- 3h signal cooldown, 3h win cooldown, 24h time-stop (a signal that
  hasn't hit TP or SL in 24h is closed at the current price).
- Sends Telegram alerts: signal alerts, TP/SL/time-stop results,
  a 4H UPDATE, a 24H PERFORMANCE report, and a WEEKLY REPORT.

## What is confirmed vs assumed

Read the header of `bot.py`. In short:

- **Confirmed** (from the original's terminal logs, Telegram messages,
  and the author's GitHub code): 10x leverage, 60s scan, 3h cooldown,
  24h time-stop, trend-only, 15 pairs, 4H+15M EMA50 entry, ADX >= 25,
  R:R 1:1.8, 2.0% account-risk cap, pandas_ta indicators
  (ATR 14, RSI 14, ADX 14, EMA 50), the report formats, the P&L formula
  (x leverage), and the career record (434W - 590L on Nov 10, 2026).
- **Assumed** (flagged [A1]-[A7] in `bot.py`): the SL multiplier (3x ATR),
  the 0-10 scoring formula, 7 of the 15 pairs, the loss cooldown (3h),
  the "Invalid Above" formula, and the stats filename (`stats.json`).

## Closing the gap with the channel history

The bot posted every signal and outcome to "Tony's signal channel" for
about a year. Exporting that history is the one thing that can replace
the remaining guesses with real data. **Done Nov 11, 2026** — Anthony
exported `result.json` (4,513 messages, Jan 9 - Nov 11, 2026) and
`parse_channel_export.py` extracted:

- **1,096 V3.0 signals** (663 SHORT, 433 LONG) across **all 15 pairs**,
  confirming the pair list (BTC 164, BNB 150, ETH 110, LTC 103, SOL 91,
  XRP 89, DOGE 75, LINK 74, AVAX 69, ADA 45, SUI 33, DOT 30, NEAR 24,
  TON 22, UNI 17).
- **1,107 outcomes**: 220 TARGET HIT, 421 STOP HIT, 400 TIME-STOP
  (218 PROFIT, 182 LOSS), plus 66 from the pre-V3.0 bot. Win rate 41.9%
  (parsed) vs 42.4% career — the bot wins ~42% of its signals.
- **R:R 1:1.8 confirmed** (median/mean/mode all 1.8 across 1,096 signals).
- **ADX >= 25 confirmed** (0 signals below 25). **Account-risk cap ~2.0%
  confirmed** (max SL distance 2.06%).
- **Labels**: "⭐⭐⭐ PREMIUM" (523) vs "⭐⭐ HIGH" (573); PREMIUM has
  higher ADX (median 36.8 vs 26.0). The score rule in `bot.py`
  reproduces the label on 86.6% of signals.
- **Career**: 435W - 591L, seeded into `stats.json` with the full
  outcome history.
- **SL multiplier**: no fixed ATR multiple reproduces the observed SL
  distances (median 1.84% of price, range 0.56-2.06%). The rebuild uses
  1.25x ATR(4h), the median of 30 sampled signals. This is the one
  formula the export could not pin down exactly.
- **"Invalid Above"**: observed factor median 0.63, mean 0.67 (wide
  spread); the rebuild uses 0.65.

To re-run the analysis: `python parse_channel_export.py
channel-export-result.json --out channel-analysis`. To re-check the SL
multiplier against historical ATR: `python fetch_atr_multipliers.py 30`.
(Note: MEXC's klines endpoint ignores `endTime` alone — both `startTime`
and `endTime` must be given; the script handles this.)

The channel also contains the **pre-V3.0 bot** (Jan - Apr 18, 2026):
different formats ("🔵 LONG DETECTED", "💰 WIN: X / Profit Secured!",
"📊 4-HOUR REPORT 📊", "🤖 Bot is active!!") and different pairs
(including PEPE/USDT). The GitHub rewrite matches that early bot, not
V3.0 — which is why its 1h timeframe, ADX 30, bounce strategy and 3x
ATR do not apply to V3.0.

## Verified (Nov 11, 2026)

- `test_bot.py` passes: indicators in range, entry logic (LONG/SHORT/
  mixed-trend/ADX-gate), risk filter (3.00% correctly skipped), and the
  report formats. The seeded 24H PERFORMANCE reproduced the real
  screenshot exactly (9 signals, 9 wins, 0 losses, 100.0%, career
  434W - 590L), and the weekly totals reproduced week 46 exactly
  (28 signals, 12W / 16L, 42.9%).
- Real MEXC data (BTC $74,422.85, BNB $686.61, Nov 11 2026) flows through
  the indicator + entry pipeline correctly; both were mixed-trend
  (4H BEARISH / 15M BULLISH) so no signal, which is correct behaviour.
- One sandbox quirk: `ccxt`'s `load_markets` call to MEXC's exchangeInfo
  fails in this sandbox (the endpoint itself returns HTTP 200 with
  1.4 MB via curl). The original bot used the same ccxt calls on Azure
  for a year, so this is an environment issue, not a bot bug. Test the
  live run on the deployment machine.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
python bot.py
```

For a safe first run, set `DRY_RUN=true` in `.env` — it prints alerts
instead of sending them. Compare its signals against the original's
Telegram history before trusting it.

## Do not run with real money

This is a signal bot (alerts only, no auto-trading). Verify it against
the original's behaviour first. The Azure recovery is still the primary
path to the true original code; this rebuild is the fallback.
