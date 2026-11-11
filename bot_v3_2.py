"""TonyBot V3.2 "Jarvis" — IMPROVED REBUILD (V3.2)
Built from bot_v3_1.py plus the V3.2 backtest (backtest_v3_2.py, Nov 11,
2026) against the 1,096 recorded V3.0 signals (1,015 matched outcomes).

V3.2 CHANGES (backtest results; V3.1 as the bot runs = 183 trades, 45.9%
win post-trailing, +0.411 R/trade, ~+6.8 R/month):
  [R1] ATR-percentile regime REPLACES the 50DMA regime filter. Only trade
      when BTC daily ATR(14) is in the normal band (20th-80th percentile
      of the trailing 90 days). Backtest: +0.560 R, 52.9% win, 138 trades,
      ~+7.0 R/month -- beats the 50DMA version on win rate, avg R and
      monthly return. Holds up out-of-sample (Jan-Jun +0.696 R, Jul-Nov
      +0.465 R). ADOPTED. (Combining 50DMA AND ATR gave +0.621 R in
      sample but fell to +0.381 R / 41.9% win in Jul-Nov, so it is NOT
      adopted; set V32_USE_50DMA=True to re-enable it.)
  [R2] Funding-rate filter: TESTED, NOT ADOPTED. MEXC funding history
      was fetched for all 15 pairs (99.8% coverage). The percentile
      filter helped a little on the V3.1 selection but failed
      out-of-sample on all trades, and absolute thresholds showed the
      opposite of the hypothesis: the most extreme-funding trades won
      59.3% at +0.204 R (high funding = strong trend = good for a
      trend-following bot). Open-interest HISTORY is unobtainable
      (MEXC OI endpoint WAF-blocked, Binance geo-blocked), so the
      funding+OI leg could not be tested at all. Do not skip
      high-funding trades.
  [R3] Partial take-profits: TESTED, NOT ADOPTED. Taking half off at
      +1.0R lifted the win rate to 55.2% (62.8% at +0.8R with the
      trailing stop), but cut avg R to +0.235 R (+0.291 R at 0.8R) from
      +0.411 R, and made unfiltered expectancy NEGATIVE. Out-of-sample
      (Jul-Nov) the win-rate lift vanished entirely (48.1% -> 48.1%)
      while avg R fell. It trades expectancy for win rate; not adopted.
  [R4] Daily ADX regime (>= 25): tested, small help (+0.443 R in the
      pipeline vs +0.411 R), but less than the ATR filter and it does
      not fix April either. NOT adopted as a separate rule; the ATR
      filter covers the regime job.
  APRIL 2026 remains untradeable chop under every regime rule tested
  (best April figure: daily ADX >= 25, 34.2% win, -0.346 R). Expect bad
  chop months to still lose; no regime rule fixes them.
  WIN-RATE NOTE: the V3.1 report's 51.4% is the PRE-trailing win rate.
  After the trailing stop converts outcomes to breakeven, V3.1's true
  win rate is 45.9% (30 breakevens). Avg R is unaffected and is the
  correct expectancy measure.
  COMBINED V3.2 backtest (all three methods stacked on V3.1: 50DMA +
  daily ADX >= 20 + funding pct + partial TP +1R + trailing BE): 99
  trades, 61.6% win, +0.346 R, +3.1 R/month -- WORSE than V3.1 on
  expectancy and monthly return despite the highest win rate. Stacking
  filters is not better; the ATR-only change above is the recommended
  V3.2. CAVEATS: in-sample backtest (filters chosen on the same data),
  so figures are likely optimistic; forward-test live before real money.

  FIDELITY FIX: the recorded signal ADX values match ADX(14) on 60-MINUTE
  candles (median abs diff 0.96 across 1,033 signals), NOT 4H (median
  abs diff ~9-10). V3.0 bot.py computed ADX from 4H candles; V3.1
  computes it from 60m candles. The trend filter still uses 4H + 15M
  EMA50s.

TonyBot V3.0 "Jarvis" — WORKING REBUILD
Built Nov 11, 2026 from Gemini's reconstruction of the original bot.py
(see bot_reconstructed_gemini.py in this folder for the verbatim source),
corrected against (a) two Telegram screenshots from the live channel,
(b) the author's GitHub rewrite (cryptotonyxyz-hash/tonybot), and
(c) a full export of "Tony's signal channel" (4,513 messages, Jan 9 -
Nov 11, 2026; 1,096 V3.0 signals parsed by parse_channel_export.py).

PROVENANCE — what is VERBATIM / CONFIRMED from the original:
  * Config: 10x leverage, 60s scan, 3h signal cooldown, 24h time-stop,
    trend ENABLED / bounce DISABLED, 15 pairs, 4H + 15M multi-timeframe.
  * Signal tracking (track_signals): TP/SL checks, state-first win/loss
    updates, cooldowns, 24h time-stop expiry, and all Telegram message
    formats — copied exactly.
  * Startup banner, "TonyBot v3.0 Online" alert, signal alert format,
    main scan loop structure — copied exactly.
  * Entry filter: LONG only when 4H BULLISH and 15M BULLISH and ADX >= 25;
    SHORT mirrored. CONFIRMED: 0 of 1,096 real signals fired below ADX 25.
  * R:R 1:1.8. CONFIRMED: median/mean/mode all 1.8 across 1,096 signals.
  * Account-risk cap ~2.0%. CONFIRMED: max observed SL distance 2.06%.
  * All 15 pairs CONFIRMED from the channel: BTC, BNB, ETH, LTC, SOL,
    XRP, DOGE, LINK, AVAX, ADA, SUI, DOT, NEAR, TON, UNI.
    (663 SHORT, 433 LONG. Most-signalled: BTC 164, BNB 150, ETH 110.)
  * REPORT FORMATS (channel export): the 4H UPDATE (Active Signals, High
    Confidence, Monitoring), the 24H PERFORMANCE (Total/Wins/Losses/
    Win Rate + Total Career), and the WEEKLY REPORT (Total/Wins/Losses/
    Win Rate + "Week N complete").
  * P&L FORMULA CONFIRMED (x leverage) from TARGET/STOP HIT messages.
  * CAREER RECORD (Nov 11, 2026): 435W - 591L (42.4% win rate).
    Outcomes: 220 TARGET HIT, 421 STOP HIT, 400 TIME-STOP (218 PROFIT,
    182 LOSS). True win rate ~42%.
  * LABELS: "⭐⭐⭐ PREMIUM" (523 signals) vs "⭐⭐ HIGH" (573 signals).
    PREMIUM has higher ADX (median 36.8 vs 26.0).
  * INDICATORS (GitHub rewrite): pandas_ta, ATR(14), RSI(14), ADX(14),
    EMA(50). The GitHub version is the author's own code, so its indicator
    setup is the best evidence for how the original computed them.
    NOTE: the GitHub rewrite matches the channel's EARLY (pre-V3.0)
    messages, so its 1h timeframe, ADX 30, bounce strategy and 3x ATR
    belong to the earlier bot, not V3.0. V3.0 values come from the channel.

ASSUMPTIONS — filled in by Muse, NOT confirmed from the original:
  [A1] Indicator math: pandas_ta ATR(14)/RSI(14)/ADX(14)/EMA(50), per the
       GitHub version. The original's exact library is unconfirmed, but the
       GitHub version is the author's own code and uses pandas_ta.
  [A2] SL = entry +/- 1.25 * ATR(4h). Median of 30 real V3.0 signals
       (range 0.69-2.02). The exact SL formula could NOT be pinned down:
       no fixed ATR multiple (4H or 15M) reproduces the observed SL
       distances, which cluster at 1.5-2.0% (median 1.84%). 1.25 is the
       best single estimate. TP = SL distance * 1.8 (confirmed).
  [A3] Score 0-10: base 6, +1 ADX >= 30, +1 ADX >= 40, +1 RSI supports
       the direction. Label: score >= 8 -> PREMIUM, else HIGH. This
       reproduces the real label on 86.6% of the 1,096 signals; the
       remaining ~13% depend on a factor the export does not reveal.
  [A4] RESOLVED — all 15 pairs confirmed from the channel export.
  [A5] LOSS_COOLDOWN_HOURS = 3 (same as win). The chat never stated the
       loss cooldown; 3h is a placeholder.
  [A6] "Invalid Above" for SHORTs = entry - 0.65 * SL distance.
       Observed median 0.63, mean 0.67 across 663 real SHORTs, but the
       spread is wide (0.11-1.89), so this is an approximation.
  [A7] stats.json is seeded from the channel export (stats_seed.json):
       435W - 591L plus the timestamped outcome history, so the 24H and
       weekly windows start from the real record instead of zero.

DO NOT RUN THIS WITH REAL MONEY. It is a signal bot (alerts only, no
auto-trading), but verify it against the original's behaviour first:
compare its signals to the original's Telegram history before trusting it.
Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in a .env file or env vars
(TELEGRAM_TOKEN / CHAT_ID also accepted).

DASHBOARD LOGGING (Nov 12, 2026): every signal is logged to the shared
SQLite store (~/workspace/projects/trading-dashboard/data/trading.db,
overridable via TRADING_DB_PATH) and every close updates that row and
appends an equity snapshot. Logging is non-fatal (failures are printed
and swallowed) and changes no trading behaviour.
"""

import os
import sqlite3
import time
import json
import traceback
from datetime import datetime, timedelta

import requests
import ccxt
import pandas as pd
import pandas_ta as ta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; env vars work without it

# =====================================================================
# CONFIGURATION & CONSTANTS  (verbatim from the original where noted)
# =====================================================================
LEVERAGE = 10
SCAN_INTERVAL_SECONDS = 60
SIGNAL_COOLDOWN_HOURS = 3
WIN_COOLDOWN_HOURS = 3
LOSS_COOLDOWN_HOURS = 3          # [A5] unconfirmed, placeholder
TIME_STOP_HOURS = 24

TREND_SIGNALS_ENABLED = True
BOUNCE_SIGNALS_ENABLED = False

# All 15 pairs CONFIRMED from the channel export (1,096 V3.0 signals,
# Apr 19 - Nov 11, 2026). The GitHub list was right; MATIC was wrong.
PAIRS_CONFIRMED = [
    "TON/USDT",
    "BNB/USDT",
    "LINK/USDT",
    "AVAX/USDT",
    "UNI/USDT",
    "NEAR/USDT",
    "BTC/USDT",
    "LTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "SUI/USDT",
]
MONITORED_PAIRS = PAIRS_CONFIRMED  # narrowed to TOP6 below (V3.1 [3])

MAX_ACCOUNT_RISK_PCT = 2.0       # reconstructed from "Skipped: Risk too high"
MIN_SIGNAL_SCORE = 6             # high-confidence threshold in 4H report
ADX_TREND_THRESHOLD = 25         # "ADX: 25.9 (Trending)"
ATR_SL_MULTIPLIER = 1.25         # [A2] ~1.25x ATR(4h) — the median of 30
                                 # real V3.0 signals (range 0.69-2.02).
                                 # NOT a clean multiple: the original's
                                 # exact SL formula could not be pinned
                                 # down. SL distances cluster at 1.5-2.0%
                                 # (median 1.84%), capped at ~2.0%.
RISK_REWARD = 1.8                # R:R 1:1.8 from Telegram alerts

# ---------------- V3.2 IMPROVEMENT FLAGS ----------------
# V3.1 flags are inherited (ADX rising, top-6, 12h cooldown, trailing BE).
# Set any flag to False/0 to reproduce V3.1 behaviour for that change.
V32_ATR_REGIME = True           # [R1] ATR-percentile regime (replaces 50DMA)
V32_ATR_LO = 0.20               # [R1] only trade when BTC daily ATR(14)
V32_ATR_HI = 0.80               #      percentile (trailing 90d) is in this band
V32_USE_50DMA = False           # [R1] ALSO require BTC vs 50DMA alignment
                                #      (tested: +0.621 R in-sample, but fell to
                                #      +0.381 R / 41.9% win in Jul-Nov; off)
V32_FUNDING_FILTER = False      # [R2] NOT adopted (see header): funding
                                #      filter failed out-of-sample and the
                                #      premise is backwards (extreme funding
                                #      trades won 59.3%). Leave off.
V32_PARTIAL_TP_R = 0.0          # [R3] NOT adopted (see header): partial TP
                                #      lifts win rate but cuts avg R and the
                                #      lift vanished out-of-sample. 0 = off.
V31_REGIME_FILTER = V32_USE_50DMA  # [1] 50DMA filter now optional (see above)
V31_ADX_RISING = True           # [2] require 60m ADX rising
V31_TOP6_ONLY = True            # [3] monitor top-6 pairs only
V31_LOSS_COOLDOWN_HOURS = 12    # [6] global cooldown after a loss (0 = off)
V31_TRAILING_BE_R = 0.8         # [5] trail stop to breakeven at +0.8R (0 = off)
V31_EARLY_EXIT_12H = False      # NOT adopted: backtest showed no help
V31_PREMIUM_ADX = 50            # [4] PREMIUM iff ADX >= 50 and regime-aligned
TOP6_PAIRS = ["BTC/USDT", "ETH/USDT", "LTC/USDT", "SOL/USDT",
              "XRP/USDT", "LINK/USDT"]
# Global post-loss cooldown timestamp (set when a trade closes a loss).
loss_cooldown_until = None
if V31_TOP6_ONLY:
    MONITORED_PAIRS = TOP6_PAIRS

STATS_FILE = "stats.json"        # [A7] filename unconfirmed

# Accept either naming convention: the reconstruction used
# TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID; the GitHub version used
# TELEGRAM_TOKEN / CHAT_ID. Prefer the reconstruction's names.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID", "")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"  # print only, no Telegram

# =====================================================================
# DASHBOARD LOGGING (TonyBot -> shared SQLite store)
# Logging only: every signal is recorded in the trades table
# (bot='tonybot') and every close updates that row + appends an equity
# snapshot. Shared store (same contract as Alpha Bot):
#   ~/workspace/projects/trading-dashboard/data/trading.db
#   TRADING_DB_PATH env var overrides the location.
# NON-FATAL BY DESIGN: any DB failure is printed and swallowed — the bot
# must never crash, stall or skip a Telegram alert because of logging.
# Behaviour note: live equity snapshots compound from $1,000 starting
# capital (or resume from the last snapshot in the DB, so they continue
# the seeded V3.2 backtest curve). pnl_pct (account %) = pnl_r x
# risk_pct, the bot's own risk model (account loss at the stop = SL
# distance as % of the account). Timestamps are ISO 8601 UTC.
# =====================================================================
DASHBOARD_DB_PATH = os.getenv(
    "TRADING_DB_PATH",
    os.path.expanduser(
        "~/workspace/projects/trading-dashboard/data/trading.db"))
DASHBOARD_BOT_NAME = "tonybot"
DASHBOARD_START_EQUITY = 1000.0
_live_equity = {"value": None}  # running account equity; None = not loaded


def _dashboard_db():
    """Open the shared store (creating dir/tables), or None on failure."""
    try:
        parent = os.path.dirname(DASHBOARD_DB_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(DASHBOARD_DB_PATH, timeout=10)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              bot TEXT NOT NULL, symbol TEXT NOT NULL,
              direction TEXT NOT NULL, signal_time TEXT NOT NULL,
              timeframe TEXT, entry REAL NOT NULL, stop REAL NOT NULL,
              target REAL NOT NULL, risk_pct REAL,
              status TEXT NOT NULL DEFAULT 'OPEN',
              exit_time TEXT, exit_price REAL, outcome TEXT,
              pnl_r REAL, pnl_pct REAL, notes TEXT)""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS equity (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              bot TEXT NOT NULL, ts TEXT NOT NULL, equity REAL NOT NULL)""")
        conn.commit()
        return conn
    except Exception as e:
        print(f"⚠️ Dashboard DB unavailable: {e}")
        return None


def _utcnow_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _signal_risk_pct(signal):
    """SL distance as % of entry price (the bot's account-risk figure)."""
    try:
        return abs(signal["entry"] - signal["sl"]) / signal["entry"] * 100.0
    except Exception:
        return None


def log_signal_to_db(signal):
    """Record a new signal as an OPEN trade. Returns the row id or None.
    Idempotent: re-logging the same (symbol, direction, signal_time)
    reuses the existing OPEN row instead of duplicating it."""
    try:
        conn = _dashboard_db()
        if conn is None:
            return None
        # Reuse the signal's first log time, so logging the same signal
        # object twice reuses its OPEN row instead of duplicating it.
        sig_time = signal.get("_db_signal_time") or _utcnow_iso()
        signal["_db_signal_time"] = sig_time
        row = conn.execute(
            "SELECT id FROM trades WHERE bot = ? AND symbol = ?"
            " AND direction = ? AND signal_time = ? AND status = 'OPEN'",
            (DASHBOARD_BOT_NAME, signal["symbol"], signal["type"],
             sig_time)).fetchone()
        if row:
            signal["_db_id"] = row[0]
            conn.close()
            return row[0]
        cur = conn.execute(
            "INSERT INTO trades (bot, symbol, direction, signal_time,"
            " timeframe, entry, stop, target, risk_pct, status, notes)"
            " VALUES (?,?,?,?,?,?,?,?,?,'OPEN',?)",
            (DASHBOARD_BOT_NAME, signal["symbol"], signal["type"],
             sig_time, "4h/15m", signal["entry"], signal["sl"],
             signal["tp"], _signal_risk_pct(signal),
             "TonyBot V3.2 live signal"))
        signal["_db_id"] = cur.lastrowid
        conn.commit()
        conn.close()
        return signal["_db_id"]
    except Exception as e:
        print(f"⚠️ Dashboard log (signal) failed: {e}")
        return None


def _find_open_trade_id(conn, signal):
    """Row id for this signal's OPEN trade: the id logged at signal time,
    else the matching OPEN row (same bot/symbol/direction/entry)."""
    trade_id = signal.get("_db_id")
    if trade_id is not None:
        return trade_id
    try:
        row = conn.execute(
            "SELECT id FROM trades WHERE bot = ? AND symbol = ?"
            " AND direction = ? AND entry = ? AND status = 'OPEN'"
            " ORDER BY id DESC LIMIT 1",
            (DASHBOARD_BOT_NAME, signal["symbol"], signal["type"],
             signal["entry"])).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def log_trade_close_to_db(signal, outcome, exit_price, pnl_r):
    """Close the signal's trade row and append an equity snapshot.
    Only the OPEN -> CLOSED transition writes equity, so a double close
    can never double-count P&L. All failures are swallowed."""
    try:
        conn = _dashboard_db()
        if conn is None:
            return
        risk_pct = _signal_risk_pct(signal)
        pnl_pct = (pnl_r * risk_pct) if (pnl_r is not None
                                         and risk_pct is not None) else None
        exit_time = _utcnow_iso()
        trade_id = _find_open_trade_id(conn, signal)
        closed = False
        if trade_id is not None:
            cur = conn.execute(
                "UPDATE trades SET status = 'CLOSED', exit_time = ?,"
                " exit_price = ?, outcome = ?, pnl_r = ?, pnl_pct = ?"
                " WHERE id = ? AND status = 'OPEN'",
                (exit_time, exit_price, outcome, pnl_r, pnl_pct, trade_id))
            closed = cur.rowcount > 0
        if closed and pnl_pct is not None:
            if _live_equity["value"] is None:
                row = conn.execute(
                    "SELECT equity FROM equity WHERE bot = ?"
                    " ORDER BY id DESC LIMIT 1",
                    (DASHBOARD_BOT_NAME,)).fetchone()
                if row is None:
                    # First snapshot ever: anchor the curve at $1,000 at
                    # the signal time so the curve starts at start capital.
                    conn.execute(
                        "INSERT INTO equity (bot, ts, equity) VALUES (?,?,?)",
                        (DASHBOARD_BOT_NAME,
                         signal.get("_db_signal_time", exit_time),
                         DASHBOARD_START_EQUITY))
                    _live_equity["value"] = DASHBOARD_START_EQUITY
                else:
                    _live_equity["value"] = float(row[0])
            _live_equity["value"] *= (1.0 + pnl_pct / 100.0)
            conn.execute(
                "INSERT INTO equity (bot, ts, equity) VALUES (?,?,?)",
                (DASHBOARD_BOT_NAME, exit_time,
                 round(_live_equity["value"], 2)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Dashboard log (close) failed: {e}")

# =====================================================================
# EXCHANGE
# =====================================================================
exchange = ccxt.mexc({'enableRateLimit': True})

tracked_signals = []
cooldowns = {}


# =====================================================================
# TELEGRAM
# =====================================================================
def send_telegram_alert(msg: str):
    """Send formatted alerts to Telegram channel."""
    if DRY_RUN or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[DRY-RUN/no-token] Telegram alert skipped:\n{msg}\n")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Error sending Telegram message: {e}")


# =====================================================================
# STATS  (redesigned from the real Telegram reports, Nov 11 screenshots)
# The original tracks lifetime W/L plus 24h and weekly windows, so every
# closed signal is recorded with a timestamp. stats.json holds:
#   wins, losses          — lifetime totals (career: 434W - 590L on Nov 10)
#   history               — [{ts: ISO time, win: bool}] for closed signals
#   last_report_4h        — 4h block already reported
#   last_report_week      — ISO week already reported
# =====================================================================
def load_stats():
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
    except Exception:
        stats = {"wins": 0, "losses": 0, "history": [],
                 "last_report_4h": None, "last_report_week": None}
    stats.setdefault("wins", 0)
    stats.setdefault("losses", 0)
    stats.setdefault("history", [])
    stats.setdefault("last_report_4h", None)
    stats.setdefault("last_report_week", None)
    return stats


def save_stats(stats):
    try:
        # Keep history bounded so the file never grows without limit.
        stats["history"] = stats.get("history", [])[-2000:]
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        print(f"⚠️ Error saving stats: {e}")


def update_win_loss(is_win: bool):
    """Update win/loss counts with State-First guarantee."""
    stats = load_stats()
    if is_win:
        stats["wins"] = stats.get("wins", 0) + 1
    else:
        stats["losses"] = stats.get("losses", 0) + 1
    stats.setdefault("history", []).append(
        {"ts": datetime.now().isoformat(), "win": bool(is_win)})
    save_stats(stats)


def _window_stats(stats, seconds):
    """Wins/losses/total/win-rate for signals closed in the last N seconds."""
    cutoff = datetime.now() - timedelta(seconds=seconds)
    recent = [h for h in stats.get("history", [])
              if datetime.fromisoformat(h["ts"]) >= cutoff]
    wins = sum(1 for h in recent if h["win"])
    losses = len(recent) - wins
    total = len(recent)
    rate = round(wins / total * 100, 1) if total else 0.0
    return total, wins, losses, rate


def _week_stats(stats, year=None, week=None):
    """Wins/losses/total/win-rate for one ISO calendar week.
    Defaults to the current week; pass a (year, week) to report a
    completed week (the WEEKLY REPORT covers the week that just ended)."""
    now = datetime.now()
    if year is None or week is None:
        year, week, _ = now.isocalendar()
    week_hist = []
    for h in stats.get("history", []):
        d = datetime.fromisoformat(h["ts"])
        y, w, _ = d.isocalendar()
        if (y, w) == (year, week):
            week_hist.append(h)
    wins = sum(1 for h in week_hist if h["win"])
    losses = len(week_hist) - wins
    total = len(week_hist)
    rate = round(wins / total * 100, 1) if total else 0.0
    return total, wins, losses, rate


# =====================================================================
# PERFORMANCE REPORTING  (format matches the real Telegram screenshots,
# Nov 10, 2026 — the reconstruction's 4H report was wrong)
# =====================================================================
def send_interval_reports():
    """4H UPDATE + 24H PERFORMANCE every 4h, plus a WEEKLY REPORT when a
    new ISO week starts. Three separate Telegram messages, in order:
      1. 4H UPDATE — active signals, high-confidence count, pair(s) monitored
      2. 24H PERFORMANCE — last 24h wins/losses/win-rate + lifetime career
      3. WEEKLY REPORT — the completed week's totals (only on week change)
    Screenshot-verified examples: 4H UPDATE 1:00 AM (Active 1, High
    Confidence 1, Monitoring BNB); 24H PERFORMANCE (Total 1, Wins 0,
    Losses 1, Win Rate 0.0%, Total Career 434W - 590L); WEEKLY REPORT
    (Total 28, Wins 12, Losses 16, Win Rate 42.9%, 'Week 46 complete')."""
    stats = load_stats()
    now = datetime.now()

    # 4H Report (once per 4h block)
    current_4h_block = str(now.hour // 4)
    if stats.get("last_report_4h") == current_4h_block:
        return

    active_count = len(tracked_signals)
    high_conf = sum(1 for s in tracked_signals if s.get("score", 0) >= 6)
    monitoring = ", ".join(sorted({s["symbol"] for s in tracked_signals})) or "-"

    msg_4h = (
        f"⏱ *4H UPDATE*\n"
        f"-------------------------\n"
        f"📊 Active Signals: {active_count}\n"
        f"⭐ High Confidence: {high_conf}\n"
        f"🔍 Monitoring: {monitoring}\n"
    )
    send_telegram_alert(msg_4h)

    # 24H PERFORMANCE (sent with the 4H update)
    total_24h, wins_24h, losses_24h, rate_24h = _window_stats(stats, 24 * 3600)
    msg_24h = (
        f"🌙 *24H PERFORMANCE*\n"
        f"-------------------------\n"
        f"📊 Total Signals: {total_24h}\n"
        f"✅ Wins: {wins_24h}\n"
        f"❌ Losses: {losses_24h}\n"
        f"📈 Win Rate: {rate_24h}%\n"
        f"-------------------------\n"
        f"🏆 Total Career: {stats.get('wins', 0)}W - {stats.get('losses', 0)}L\n"
    )
    send_telegram_alert(msg_24h)

    # WEEKLY REPORT (once, when a new ISO week starts)
    year, week, _ = now.isocalendar()
    if stats.get("last_report_week") != week:
        prev = now - timedelta(days=7)
        prev_year, prev_week, _ = prev.isocalendar()
        total_w, wins_w, losses_w, rate_w = _week_stats(stats, prev_year, prev_week)
        msg_week = (
            f"📊 *WEEKLY REPORT*\n"
            f"-------------------------\n"
            f"📊 Total Signals: {total_w}\n"
            f"✅ Wins: {wins_w}\n"
            f"❌ Losses: {losses_w}\n"
            f"📈 Win Rate: {rate_w}%\n"
            f"-------------------------\n"
            f"Week {prev_week} complete. New week starting!\n"
        )
        send_telegram_alert(msg_week)
        stats["last_report_week"] = week

    stats["last_report_4h"] = current_4h_block
    save_stats(stats)


# =====================================================================
# TECHNICAL INDICATORS  [A1] pandas_ta — the same library + periods as
# the author's GitHub version: ATR(14), RSI(14), ADX(14), EMA(50).
# The GitHub version's indicator setup is the best evidence for how the
# original computed them, and it matches every indicator name in the
# terminal logs. Verified working (pandas_ta 0.3.x).
# =====================================================================
def compute_indicators(ohlcv):
    """Return a dict of indicator values from OHLCV candles.
    ohlcv: list of [timestamp, open, high, low, close, volume].
    Returns ADX(14), RSI(14), ATR(14) and EMA(50) for the last candle,
    plus the ATR as a % of the last close."""
    df = pd.DataFrame(
        ohlcv, columns=["ts", "open", "high", "low", "close", "volume"]
    )
    df["atr"] = df.ta.atr(length=14)
    df["rsi"] = df.ta.rsi(length=14)
    adx_df = df.ta.adx(length=14)
    df["adx"] = adx_df["ADX_14"]
    df["ema50"] = df.ta.ema(length=50)

    close_last = float(df["close"].iloc[-1])
    atr_val = float(df["atr"].iloc[-1])

    return {
        "adx": float(df["adx"].iloc[-1]),
        "rsi": float(df["rsi"].iloc[-1]),
        "atr": atr_val,
        "atr_pct": atr_val / close_last * 100,
        "ema50": float(df["ema50"].iloc[-1]),
        "price": close_last,
    }


# Cache for the BTC regime (refreshed at most once an hour).
_regime_cache = {"ts": None, "bullish": None}


def get_btc_regime():
    """V3.1 [1] Market regime: True if BTC's last completed daily close is
    above its 50-day moving average, False if below, None if unknown.
    Cached for 1h; fail-open (None) on any fetch error."""
    now = datetime.now()
    if _regime_cache["ts"] is not None and (now - _regime_cache["ts"]).seconds < 3600:
        return _regime_cache["bullish"]
    try:
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", timeframe="1d", limit=60)
        closes = pd.Series([c[4] for c in ohlcv])
        if len(closes) < 50:
            return None
        ma50 = closes.rolling(50).mean().iloc[-1]
        bullish = bool(closes.iloc[-1] > ma50)
    except Exception as e:
        print(f"⚠️ Regime check failed: {e}")
        return None
    _regime_cache["ts"] = now
    _regime_cache["bullish"] = bullish
    return bullish


# Cache for the BTC ATR-percentile regime (refreshed at most once an hour).
_atr_pct_cache = {"ts": None, "pct": None}


def get_btc_atr_pct():
    """V3.2 [R1] Volatility regime: the percentile of BTC's latest daily
    ATR(14) within the trailing 90 days (0.0-1.0). Normal volatility is
    0.20-0.80; below 0.20 the market is compressed, above 0.80 it is in
    an extreme-volatility regime. Backtest: trading only inside
    [0.20, 0.80] gave +0.560 R / 52.9% win (vs +0.411 R / 45.9% for the
    50DMA regime) and held up out-of-sample (Jan-Jun +0.696 R, Jul-Nov
    +0.465 R). Cached for 1h; fail-open (None) on any fetch error."""
    now = datetime.now()
    if _atr_pct_cache["ts"] is not None and (now - _atr_pct_cache["ts"]).seconds < 3600:
        return _atr_pct_cache["pct"]
    try:
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", timeframe="1d", limit=150)
        df = pd.DataFrame(
            ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df["atr"] = df.ta.atr(length=14)
        atrs = df["atr"].dropna()
        if len(atrs) < 91:
            return None
        # Percentile of the LATEST ATR vs the trailing 90 days BEFORE it
        # (excluding today, matching backtest_v3_2.btc_daily_features).
        latest = float(atrs.iloc[-1])
        window = atrs.iloc[-91:-1]
        pct = float((window <= latest).sum() / len(window))
    except Exception as e:
        print(f"⚠️ ATR-percentile check failed: {e}")
        return None
    _atr_pct_cache["ts"] = now
    _atr_pct_cache["pct"] = pct
    return pct


def fetch_indicator_data(symbol):
    """Fetch 4H + 15M candles and compute multi-timeframe indicators.
    V3.1 FIDELITY FIX: ADX comes from 60M candles, not 4H -- the recorded
    signal ADX values match 60m ADX(14) (median abs diff 0.96), while 4H
    ADX(14) is off by ~9 points. Also returns the 60m ADX one candle ago
    (for the ADX-rising filter) and the BTC regime."""
    try:
        ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=200)
        ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=200)
        ohlcv_60m = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=200)
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        ind_4h = compute_indicators(ohlcv_4h)
        ind_15m = compute_indicators(ohlcv_15m)
        ind_60m = compute_indicators(ohlcv_60m)
        # ADX one 60m candle ago (for the rising filter).
        df_60m = pd.DataFrame(
            ohlcv_60m, columns=["ts", "open", "high", "low", "close", "volume"])
        adx_series = df_60m.ta.adx(length=14)["ADX_14"]
        adx_prev = float(adx_series.iloc[-2]) if len(adx_series) >= 2 else None

        trend_4h = "BULLISH" if current_price >= ind_4h["ema50"] else "BEARISH"
        trend_15m = "BULLISH" if current_price >= ind_15m["ema50"] else "BEARISH"

        return {
            "price": current_price,
            "adx": ind_60m["adx"],       # V3.1: 60m ADX (was 4H in V3.0)
            "adx_prev": adx_prev,
            "rsi": ind_4h["rsi"],
            "atr": ind_4h["atr"],
            "atr_pct": ind_4h["atr_pct"],
            "trend_4h": trend_4h,
            "trend_15m": trend_15m,
            "ema50_4h": ind_4h["ema50"],
            "ema50_15m": ind_15m["ema50"],
            "regime_bullish": get_btc_regime(),
            "atr_pct90": get_btc_atr_pct(),   # V3.2 [R1] BTC daily ATR(14)
                                              # percentile vs trailing 90d
        }
    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")
        traceback.print_exc()
        return None


def score_signal(trade_type, adx, rsi, regime_aligned=None):
    """Score 0-10 + confidence label.
    V3.1 [4] LABEL REBUILT: the old score>=8 rule was meaningless
    (PREMIUM 41.4% win vs HIGH 43.0% on 1,015 matched trades). The new
    rule -- PREMIUM iff ADX >= 50 AND the trade aligns with the BTC
    regime -- separates winners (22 trades, 59.1% win, +0.553 R) from
    the rest (41.9% win, +0.006 R). The score itself is unchanged
    (base 6, +1 ADX >= 30, +1 ADX >= 40, +1 RSI supports direction)
    and is still shown in the alert; only the label rule changed.
    regime_aligned=None (unknown regime) falls back to the old rule."""
    score = 6
    if adx >= 30:
        score += 1
    if adx >= 40:
        score += 1
    if (trade_type == "LONG" and rsi > 50) or (trade_type == "SHORT" and rsi < 50):
        score += 1
    score = min(score, 10)
    if regime_aligned is None:
        label = "PREMIUM" if score >= 8 else "HIGH"
    else:
        label = "PREMIUM" if (adx >= V31_PREMIUM_ADX and regime_aligned) else "HIGH"
    return score, label


def evaluate_signal(symbol, data):
    """Evaluate entry conditions for trend-following signals.
    Entry rule (verbatim from reconstruction): LONG only when 4H BULLISH
    and 15M BULLISH and ADX >= 25; SHORT mirrored. SL/TP per [A2]."""
    price = data["price"]
    adx = data["adx"]
    trend_4h = data["trend_4h"]
    trend_15m = data["trend_15m"]

    global loss_cooldown_until
    if symbol in cooldowns and datetime.now() < cooldowns[symbol]:
        return None

    # V3.1 [6] Global post-loss cooldown (starts at the loss close).
    if (V31_LOSS_COOLDOWN_HOURS > 0 and loss_cooldown_until is not None
            and datetime.now() < loss_cooldown_until):
        return None

    if not TREND_SIGNALS_ENABLED:
        return None

    # V3.1 [2] ADX must be rising (60m ADX now > one 60m candle ago).
    if V31_ADX_RISING:
        adx_prev = data.get("adx_prev")
        if adx_prev is not None and not (adx > adx_prev):
            return None

    # V3.2 [R1] Volatility regime: only trade when BTC daily ATR(14) is
    # in the normal band [V32_ATR_LO, V32_ATR_HI] of its trailing 90-day
    # percentile. This REPLACES the 50DMA regime filter (which could not
    # catch chop). Fail-open on unknown (None).
    if V32_ATR_REGIME:
        atr_pct90 = data.get("atr_pct90")
        if atr_pct90 is not None and not (V32_ATR_LO <= atr_pct90 <= V32_ATR_HI):
            return None

    # V3.1 [1] Regime (optional in V3.2): only trade with the macro BTC
    # trend. Off by default -- combining it with the ATR filter gave a
    # higher in-sample R but did not hold up out-of-sample.
    regime_bullish = data.get("regime_bullish")
    regime_aligned = None
    trade_type = None
    if trend_4h == "BULLISH" and trend_15m == "BULLISH" and adx >= ADX_TREND_THRESHOLD:
        trade_type = "LONG"
        if regime_bullish is not None:
            regime_aligned = bool(regime_bullish)
    elif trend_4h == "BEARISH" and trend_15m == "BEARISH" and adx >= ADX_TREND_THRESHOLD:
        trade_type = "SHORT"
        if regime_bullish is not None:
            regime_aligned = not bool(regime_bullish)
    else:
        return None
    if V31_REGIME_FILTER and regime_aligned is False:
        return None

    # [A2] SL = 1.25 * ATR(4h) (median of 30 real V3.0 signals; the exact
    # formula could not be pinned down). TP = SL distance * 1.8 (R:R 1:1.8,
    # confirmed: median/mean/mode all 1.8 across 1,096 signals).
    sl_distance = ATR_SL_MULTIPLIER * data["atr"]
    if trade_type == "LONG":
        sl = price - sl_distance
        tp = price + (sl_distance * RISK_REWARD)
        invalid_above = None
    else:
        sl = price + sl_distance
        tp = price - (sl_distance * RISK_REWARD)
        # [A6] "Invalid Above" factor: observed median 0.63, mean 0.67
        # across 663 real SHORTs (wide spread, 0.11-1.89 — not a fixed
        # fraction; 0.65 is the best single estimate).
        invalid_above = price - (sl_distance * 0.65)

    # Account risk check (e.g. "Skipped: Risk too high (2.56% account)")
    account_risk_pct = sl_distance / price * 100
    if account_risk_pct > MAX_ACCOUNT_RISK_PCT:
        print(f"⚠️ Skipped: Risk too high ({account_risk_pct:.2f}% account)")
        return None

    score, label = score_signal(trade_type, adx, data["rsi"], regime_aligned)  # V3.1 [4]

    return {
        "symbol": symbol,
        "type": trade_type,
        "entry": price,
        "trail_armed": False,   # V3.1 [5] trailing stop state
        "be_stop": None,
        "tp": tp,
        "sl": sl,
        "invalid_above": invalid_above,
        "score": score,
        "label": label,
        "start_time": datetime.now(),
        "adx": adx,
        "rsi": data["rsi"],
        "atr_pct": data["atr_pct"],
        "trend_4h": trend_4h,
        "trend_15m": trend_15m,
        "risk_reward": "1:1.8",
        "account_risk": f"{account_risk_pct:.2f}%"
    }


# =====================================================================
# SIGNAL TRACKING & 24H TIME-STOP  (verbatim from the original)
# =====================================================================
def track_signals():
    """Monitor open signals for TP/SL and 24h Time-Stops with improved safety"""
    to_remove = []

    for signal in tracked_signals:
        try:
            symbol = signal['symbol']
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']

            # V3.1 [5] Trailing stop to breakeven: once the trade reaches
            # +0.8R in its favour, the stop trails to the entry price. If
            # price comes back to the entry, exit at breakeven (~0R) instead
            # of riding it to a full stop. Safe to check before TP/SL: the
            # breakeven exit needs price back AT the entry, while TP needs
            # price at the target, so the two can never fire together.
            if V31_TRAILING_BE_R > 0:
                sl_dist = abs(signal['entry'] - signal['sl'])
                if sl_dist > 0:
                    if signal['type'] == "LONG":
                        lvl = signal['entry'] + V31_TRAILING_BE_R * sl_dist
                        if not signal.get('trail_armed') and current_price >= lvl:
                            signal['trail_armed'] = True
                            signal['be_stop'] = signal['entry']
                        if signal.get('trail_armed') and current_price <= signal['entry']:
                            cooldowns[symbol] = datetime.now() + timedelta(hours=WIN_COOLDOWN_HOURS)
                            to_remove.append(signal)
                            log_trade_close_to_db(signal, "BREAKEVEN", signal['entry'], 0.0)
                            msg = (f"🔄 *TRAILING STOP (breakeven): {symbol}*\n"
                                   f"{signal['type']} closed at entry after reaching "
                                   f"+{V31_TRAILING_BE_R}R\n Entry: `{signal['entry']:.4f}`")
                            send_telegram_alert(msg)
                            continue
                    else:
                        lvl = signal['entry'] - V31_TRAILING_BE_R * sl_dist
                        if not signal.get('trail_armed') and current_price <= lvl:
                            signal['trail_armed'] = True
                            signal['be_stop'] = signal['entry']
                        if signal.get('trail_armed') and current_price >= signal['entry']:
                            cooldowns[symbol] = datetime.now() + timedelta(hours=WIN_COOLDOWN_HOURS)
                            to_remove.append(signal)
                            log_trade_close_to_db(signal, "BREAKEVEN", signal['entry'], 0.0)
                            msg = (f"🔄 *TRAILING STOP (breakeven): {symbol}*\n"
                                   f"{signal['type']} closed at entry after reaching "
                                   f"+{V31_TRAILING_BE_R}R\n Entry: `{signal['entry']:.4f}`")
                            send_telegram_alert(msg)
                            continue

            # 1. Check Take Profit (TP)
            if (signal['type'] == "LONG" and current_price >= signal['tp']) or \
               (signal['type'] == "SHORT" and current_price <= signal['tp']):

                # STATE UPDATE FIRST (Protection against double-counting)
                update_win_loss(True)
                cooldowns[symbol] = datetime.now() + timedelta(hours=WIN_COOLDOWN_HOURS)
                to_remove.append(signal)
                log_trade_close_to_db(signal, "TARGET_HIT", signal['tp'], RISK_REWARD)

                # NETWORK CALLS SECOND
                pnl = round(abs(signal['tp'] - signal['entry']) / signal['entry'] * LEVERAGE * 100, 1)
                msg = f"💰 *TARGET HIT: {symbol}*\n✅ {signal['type']} Closed in Profit\n Entry: `{signal['entry']:.4f}`\n Exit: `{signal['tp']}`"
                send_telegram_alert(msg)
                continue

            # 2. Check Stop Loss (SL)
            if (signal['type'] == "LONG" and current_price <= signal['sl']) or \
               (signal['type'] == "SHORT" and current_price >= signal['sl']):

                # STATE UPDATE FIRST
                update_win_loss(False)
                cooldowns[symbol] = datetime.now() + timedelta(hours=LOSS_COOLDOWN_HOURS)
                global loss_cooldown_until
                if V31_LOSS_COOLDOWN_HOURS > 0:
                    loss_cooldown_until = datetime.now() + timedelta(hours=V31_LOSS_COOLDOWN_HOURS)
                to_remove.append(signal)
                log_trade_close_to_db(signal, "STOP_HIT", signal['sl'], -1.0)

                # NETWORK CALLS SECOND
                pnl = round(abs(signal['sl'] - signal['entry']) / signal['entry'] * LEVERAGE * 100, 1)
                msg = f"❌ *STOP HIT: {symbol}*\n🛑 {signal['type']} Stopped Out\n Entry: `{signal['entry']:.4f}`\n Exit: `{signal['sl']:.4f}`"
                send_telegram_alert(msg)
                continue

            # 3. Time-Stop Expiry (24h Limit)
            if datetime.now() - signal['start_time'] > timedelta(hours=24):

                if signal['type'] == "LONG":
                    expiry_pnl = ((current_price - signal['entry']) / signal['entry']) * 100 * LEVERAGE
                else:
                    expiry_pnl = ((signal['entry'] - current_price) / signal['entry']) * 100 * LEVERAGE

                is_win = expiry_pnl > 0

                # STATE UPDATE FIRST
                update_win_loss(is_win)
                cd_hours = WIN_COOLDOWN_HOURS if is_win else LOSS_COOLDOWN_HOURS
                cooldowns[symbol] = datetime.now() + timedelta(hours=cd_hours)
                if not is_win and V31_LOSS_COOLDOWN_HOURS > 0:
                    loss_cooldown_until = datetime.now() + timedelta(hours=V31_LOSS_COOLDOWN_HOURS)
                to_remove.append(signal)
                # Dashboard log: R from the leveraged time-stop P&L
                # (R = pnl_pct / (sl_dist_pct x 10), as in the backtest).
                _sl_dist_pct = abs(signal['entry'] - signal['sl']) / signal['entry'] * 100.0
                _pnl_r = expiry_pnl / (_sl_dist_pct * 10.0) if _sl_dist_pct else 0.0
                log_trade_close_to_db(signal, "TIME_STOP", current_price, _pnl_r)

                # NETWORK CALLS SECOND
                status_emoji = "🟢" if is_win else "🔴"
                msg = (
                    f"⏱ *TIME-STOP EXPIRED: {symbol}*\n"
                    f"-------------------------\n"
                    f"Result: {status_emoji} {'PROFIT' if is_win else 'LOSS'}\n"
                    f" Entry: `{signal['entry']:.4f}`\n"
                    f" Exit: `{current_price:.4f}`\n"
                    f" Final P&L: **{expiry_pnl:+.1f}%**"
                )
                send_telegram_alert(msg)

        except Exception as e:
            print(f"⚠️ Error tracking {signal['symbol']}: {e}")

    # Safely clear removed signals
    for s in to_remove:
        if s in tracked_signals:
            tracked_signals.remove(s)


# =====================================================================
# MAIN SCAN LOOP & STARTUP BANNER  (verbatim from the original)
# =====================================================================
def print_startup_banner():
    """Print startup service banner to console."""
    print("==================================================")
    print("🤖 TONYBOT V3.1 – PROFESSIONAL SIGNAL SERVICE")
    print(f"🛡 Regime filter: {'ON' if V31_REGIME_FILTER else 'OFF'} | "
          f"ADX rising: {'ON' if V31_ADX_RISING else 'OFF'} | "
          f"Top-6 only: {'ON' if V31_TOP6_ONLY else 'OFF'}")
    print(f"⏱ Post-loss cooldown: {V31_LOSS_COOLDOWN_HOURS}h | "
          f"Trailing BE: +{V31_TRAILING_BE_R}R")
    print("==================================================")
    print(f"📊 Monitoring: {len(MONITORED_PAIRS)} pairs")
    print(f"⚡ Trend Signals: {'ENABLED' if TREND_SIGNALS_ENABLED else 'DISABLED'}")
    print(f"🔄 Bounce Signals: {'ENABLED' if BOUNCE_SIGNALS_ENABLED else 'DISABLED'}")
    print(f"⏱ Signal Cooldown: {SIGNAL_COOLDOWN_HOURS}h")
    print("==================================================\n")


def send_online_alert():
    """Send startup message to Telegram channel."""
    online_msg = (
        "🤖 TonyBot v3.0 Online\n"
        "------------------------------------\n"
        "✅ Professional Signal Service\n"
        "📊 Monitoring 15 pairs\n"
        "⭐ Premium trend signals only\n"
        "⚙️ Multi-timeframe confirmation\n\n"
        "Ready to scan markets..."
    )
    send_telegram_alert(online_msg)


def run_bot():
    """Main execution loop."""
    print_startup_banner()
    send_online_alert()

    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("==================================================")
            print(f"🔚 Scan Cycle: {now_str}")
            print(f"📊 Active Signals: {len(tracked_signals)}")
            print("==================================================\n")

            # 1. Track currently open signals (TP, SL, 24h Time-Stop)
            track_signals()

            # 2. Scan pairs for new signals
            for symbol in MONITORED_PAIRS:
                print(f"🔍 Analyzing {symbol}...")
                data = fetch_indicator_data(symbol)
                if not data:
                    time.sleep(1)
                    continue

                print(f"📊 ADX: {data['adx']:.1f} | RSI: {data['rsi']:.1f} | ATR: {data['atr_pct']:.2f}%")
                print(f"└ 4H Trend: {data['trend_4h']} (Price: {data['price']}, EMA50: {data['ema50_4h']:.2f})")
                print(f"└ 15M Trend: {data['trend_15m']} (Price: {data['price']}, EMA50: {data['ema50_15m']:.2f})")

                signal = evaluate_signal(symbol, data)
                if signal:
                    tracked_signals.append(signal)
                    log_signal_to_db(signal)

                    # Verbatim V3.0 signal alert format, from the channel
                    # export (e.g. DOGE SHORT, 2026-04-19). The label is
                    # "⭐⭐⭐ PREMIUM" (score >= 8) or "⭐⭐ HIGH" (score 6-7).
                    stars = "⭐⭐⭐" if signal['label'] == 'PREMIUM' else "⭐⭐"
                    alert_text = (
                        f"🔻 SHORT SIGNAL: {signal['symbol']}\n" if signal['type'] == 'SHORT' else f"🔺 LONG SIGNAL: {signal['symbol']}\n"
                    )
                    alert_text += (
                        f"{stars} {signal['label']}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📍 Entry: {signal['entry']:.4f}\n"
                        f"🎯 Target: {signal['tp']:.4f}\n"
                        f"🛑 Stop Loss: {signal['sl']:.4f}\n"
                    )
                    if signal['invalid_above']:
                        alert_text += f"❌ Invalid Above: {signal['invalid_above']:.4f}\n"
                    alert_text += (
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 Indicators:\n"
                        f"  • ADX: {signal['adx']:.1f} (Trending)\n"
                        f"  • RSI: {signal['rsi']:.1f}\n"
                        f"  • 4H: {signal['trend_4h']}\n"
                        f"  • 15M: {signal['trend_15m']}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"⚖️ Risk Management:\n"
                        f"  • Leverage: {LEVERAGE}x\n"
                        f"  • Account Risk: {signal['account_risk']}\n"
                        f"  • Risk/Reward: {signal['risk_reward']}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🕐 Signal Time: {datetime.utcnow().strftime('%H:%M:%S')} UTC\n"
                        f"⏰ Entry Window: 15 minutes\n"
                        f"⏳ Valid For: {TIME_STOP_HOURS} hours"
                    )
                    send_telegram_alert(alert_text)
                    print(f"✅ SIGNAL SENT: {symbol} {signal['type']} (Score: {signal['score']}/10, {signal['label']})")

                time.sleep(1)  # rate-limit pause between pairs (GitHub version)

            # 3. Process periodic reports
            send_interval_reports()

            print("\n✅ Cycle complete. Next scan in 60s...\n")
            time.sleep(SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n🛑 Shutting down gracefully...")
            offline_msg = (
                "🔴 TonyBot v3.0 Offline\n"
                "Manual shutdown initiated."
            )
            send_telegram_alert(offline_msg)
            break
        except Exception as e:
            print(f"❌ Unhandled error in main loop: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    run_bot()
