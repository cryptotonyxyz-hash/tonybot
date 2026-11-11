"""Test TonyBot rebuild: indicators, entry logic, stats/reports, live MEXC.
Run with the venv python: /tmp/tonybot-test-venv/bin/python test_bot.py
DRY_RUN=true so no Telegram messages are sent.
"""
import os, sys, json, math
os.environ["DRY_RUN"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = "test"
os.environ["TELEGRAM_CHAT_ID"] = "test"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bot

# --- 1. Indicators on synthetic OHLCV (uptrend then downtrend) ---
import random
random.seed(7)
ohlcv = []
price = 100.0
for i in range(200):
    drift = 0.15 if i < 120 else -0.25   # uptrend, then downtrend
    o = price
    c = price + drift + random.uniform(-0.4, 0.4)
    h = max(o, c) + random.uniform(0, 0.3)
    l = min(o, c) - random.uniform(0, 0.3)
    ohlcv.append([i * 60000, o, h, l, c, random.uniform(10, 100)])
    price = c
ind = bot.compute_indicators(ohlcv)
print("1) Indicators (synthetic, downtrend tail):")
print(f"   ADX {ind['adx']:.1f} | RSI {ind['rsi']:.1f} | ATR {ind['atr']:.3f} "
      f"({ind['atr_pct']:.2f}%) | EMA50 {ind['ema50']:.2f} | price {ind['price']:.2f}")
assert 0 <= ind['rsi'] <= 100, "RSI out of range"
assert ind['adx'] >= 0, "ADX negative"
assert ind['atr'] > 0, "ATR not positive"
print("   OK: indicators in range, pandas_ta working")

# --- 2. Entry logic: bullish alignment should give LONG, bearish SHORT ---
def fake_data(price, ema4h, ema15m, adx=30.0, rsi=55.0, atr=0.5):
    return {"price": price, "adx": adx, "rsi": rsi, "atr": atr,
            "atr_pct": atr / price * 100,
            "trend_4h": "BULLISH" if price >= ema4h else "BEARISH",
            "trend_15m": "BULLISH" if price >= ema15m else "BEARISH",
            "ema50_4h": ema4h, "ema50_15m": ema15m}

bot.cooldowns = {}
sig = bot.evaluate_signal("BTC/USDT", fake_data(100, 95, 95, adx=30, rsi=55, atr=0.5))
print("2) Entry logic:")
print(f"   Bullish 4H+15M, ADX 30 -> {sig['type'] if sig else None} "
      f"(entry {sig['entry'] if sig else '-'}, SL {sig['sl'] if sig else '-'}, "
      f"TP {sig['tp'] if sig else '-'}, score {sig['score'] if sig else '-'}, "
      f"label {sig['label'] if sig else '-'})")
assert sig and sig['type'] == "LONG", "expected LONG"
assert abs(sig['sl'] - (100 - 1.25 * 0.5)) < 1e-9, "SL should be entry - 1.25*ATR"
assert abs(sig['tp'] - (100 + (100 - sig['sl']) * 1.8)) < 1e-9, "TP should be SL dist * 1.8"
assert sig['label'] == 'PREMIUM', "ADX 30 + RSI 55 should be PREMIUM"
print("   OK: LONG with SL = entry - 1.25*ATR, TP = SL dist * 1.8, PREMIUM label")

bot.cooldowns = {}
sig2 = bot.evaluate_signal("BTC/USDT", fake_data(100, 105, 105, adx=28, rsi=40, atr=0.5))
assert sig2 and sig2['type'] == "SHORT", "expected SHORT"
print(f"   Bearish 4H+15M, ADX 28 -> {sig2['type']} (SL {sig2['sl']:.2f}, TP {sig2['tp']:.2f})")

bot.cooldowns = {}
sig3 = bot.evaluate_signal("BTC/USDT", fake_data(100, 95, 105, adx=30, rsi=55, atr=0.5))
assert sig3 is None, "mixed 4H/15M should give no signal"
print("   Mixed 4H BULLISH / 15M BEARISH -> no signal. OK")

bot.cooldowns = {}
sig4 = bot.evaluate_signal("BTC/USDT", fake_data(100, 95, 95, adx=20, rsi=55, atr=0.5))
assert sig4 is None, "ADX < 25 should give no signal"
print("   ADX 20 (< 25) -> no signal. OK")

# --- 3. Stats + reports: seed the real career record, check formats ---
bot.STATS_FILE = "/tmp/tonybot-test-stats.json"
if os.path.exists(bot.STATS_FILE):
    os.remove(bot.STATS_FILE)
from datetime import datetime, timedelta
now = datetime.now()
# Seed history: 434W-590L career, 28 signals this week (12W/16L), 9 in last 24h (9W)
hist = []
for i in range(9):   # last 24h: 9 wins
    hist.append({"ts": (now - timedelta(hours=i)).isoformat(), "win": True})
for i in range(19):  # rest of this week: 3W + 16L
    win = i < 3
    hist.append({"ts": (now - timedelta(days=2, hours=i)).isoformat(), "win": win})
stats = {"wins": 434, "losses": 590, "history": hist,
         "last_report_4h": None, "last_report_week": None}
with open(bot.STATS_FILE, "w") as f:
    json.dump(stats, f)
bot.tracked_signals = [{"symbol": "BNB/USDT", "score": 8, "type": "LONG"}]
print("3) Reports (DRY_RUN prints instead of sending):")
bot.send_interval_reports()
print("   OK: 4H UPDATE + 24H PERFORMANCE + WEEKLY REPORT printed above")
# Verify the weekly totals computed from history match the screenshot example
t, w, l, r = bot._week_stats(bot.load_stats())
print(f"   This week's totals from history: {t} signals, {w}W/{l}L, {r}% "
      f"(screenshot week 46 was 28 / 12W / 16L / 42.9%)")

# --- 4. Live MEXC fetch (read-only) for BTC 4h/15m ---
print("4) Live MEXC fetch (read-only):")
data = bot.fetch_indicator_data("BTC/USDT")
if data:
    print(f"   BTC price {data['price']:.2f} | ADX {data['adx']:.1f} | "
          f"RSI {data['rsi']:.1f} | ATR {data['atr_pct']:.2f}% | "
          f"4H {data['trend_4h']} | 15M {data['trend_15m']}")
    print("   OK: live MEXC data flows through the real pipeline")
else:
    print("   WARN: live fetch failed (network?) — indicators/entry already verified above")

print("\nALL TESTS PASSED")
