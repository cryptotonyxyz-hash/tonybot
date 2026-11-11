"""TonyBot V3.0 "Jarvis" — WORKING REBUILD
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
"""

import os
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
MONITORED_PAIRS = PAIRS_CONFIRMED

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

STATS_FILE = "stats.json"        # [A7] filename unconfirmed

# Accept either naming convention: the reconstruction used
# TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID; the GitHub version used
# TELEGRAM_TOKEN / CHAT_ID. Prefer the reconstruction's names.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID", "")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"  # print only, no Telegram

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


def fetch_indicator_data(symbol):
    """Fetch 4H + 15M candles and compute multi-timeframe indicators."""
    try:
        ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=200)
        ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=200)
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        ind_4h = compute_indicators(ohlcv_4h)
        ind_15m = compute_indicators(ohlcv_15m)

        trend_4h = "BULLISH" if current_price >= ind_4h["ema50"] else "BEARISH"
        trend_15m = "BULLISH" if current_price >= ind_15m["ema50"] else "BEARISH"

        return {
            "price": current_price,
            "adx": ind_4h["adx"],
            "rsi": ind_4h["rsi"],
            "atr": ind_4h["atr"],
            "atr_pct": ind_4h["atr_pct"],
            "trend_4h": trend_4h,
            "trend_15m": trend_15m,
            "ema50_4h": ind_4h["ema50"],
            "ema50_15m": ind_15m["ema50"],
        }
    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")
        traceback.print_exc()
        return None


def score_signal(trade_type, adx, rsi):
    """[A3] Score 0-10 + confidence label, calibrated on 1,096 real V3.0
    signals from the channel export. Base 6 for a valid trend signal;
    +1 ADX >= 30; +1 ADX >= 40; +1 if RSI supports the direction
    (LONG: RSI > 50, SHORT: RSI < 50). Label: score >= 8 -> PREMIUM
    (3 stars, 523 signals), score 6-7 -> HIGH (2 stars, 573 signals).
    This rule reproduces the real label on 86.6% of signals; the
    remaining ~13% depend on a factor the export does not reveal.
    All signals are score >= 6, so every signal counts as high
    confidence in the 4H UPDATE."""
    score = 6
    if adx >= 30:
        score += 1
    if adx >= 40:
        score += 1
    if (trade_type == "LONG" and rsi > 50) or (trade_type == "SHORT" and rsi < 50):
        score += 1
    score = min(score, 10)
    label = "PREMIUM" if score >= 8 else "HIGH"
    return score, label


def evaluate_signal(symbol, data):
    """Evaluate entry conditions for trend-following signals.
    Entry rule (verbatim from reconstruction): LONG only when 4H BULLISH
    and 15M BULLISH and ADX >= 25; SHORT mirrored. SL/TP per [A2]."""
    price = data["price"]
    adx = data["adx"]
    trend_4h = data["trend_4h"]
    trend_15m = data["trend_15m"]

    if symbol in cooldowns and datetime.now() < cooldowns[symbol]:
        return None

    if not TREND_SIGNALS_ENABLED:
        return None

    trade_type = None
    if trend_4h == "BULLISH" and trend_15m == "BULLISH" and adx >= ADX_TREND_THRESHOLD:
        trade_type = "LONG"
    elif trend_4h == "BEARISH" and trend_15m == "BEARISH" and adx >= ADX_TREND_THRESHOLD:
        trade_type = "SHORT"
    else:
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

    score, label = score_signal(trade_type, adx, data["rsi"])  # [A3]

    return {
        "symbol": symbol,
        "type": trade_type,
        "entry": price,
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

            # 1. Check Take Profit (TP)
            if (signal['type'] == "LONG" and current_price >= signal['tp']) or \
               (signal['type'] == "SHORT" and current_price <= signal['tp']):

                # STATE UPDATE FIRST (Protection against double-counting)
                update_win_loss(True)
                cooldowns[symbol] = datetime.now() + timedelta(hours=WIN_COOLDOWN_HOURS)
                to_remove.append(signal)

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
                to_remove.append(signal)

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
                to_remove.append(signal)

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
    print("🤖 TONYBOT V3.0 – PROFESSIONAL SIGNAL SERVICE")
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
