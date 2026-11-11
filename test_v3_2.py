"""Tests for bot_v3_2.py (the V3.2 improved rebuild).

Tests the new logic only (no network, no Telegram): the ATR-percentile
regime gate, the 50DMA filter being optional/off by default, and the
funding / partial-TP flags being off by default. The ATR percentile
itself is verified against the backtest's regime_v2_at() on the local
BTC daily klines. Run with:
  DRY_RUN=true /tmp/tonybot-test-venv/bin/python test_v3_2.py
"""
import json
import os
import sys
from datetime import datetime

os.environ["DRY_RUN"] = "true"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bot_v3_2 as b

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def base_data(**over):
    d = {
        "price": 100.0,
        "adx": 35.0,
        "adx_prev": 30.0,          # rising
        "rsi": 60.0,
        "atr": 1.5,
        "atr_pct": 1.5,
        "trend_4h": "BULLISH",
        "trend_15m": "BULLISH",
        "ema50_4h": 95.0,
        "ema50_15m": 98.0,
        "regime_bullish": True,
        "atr_pct90": 0.50,         # in-band
    }
    d.update(over)
    return d


print("== 1. ATR-percentile regime gate ==")
b.cooldowns.clear()
b.loss_cooldown_until = None
sig = b.evaluate_signal("BTC/USDT", base_data(atr_pct90=0.50))
check("atr_pct90 0.50 (in band) -> signal", sig is not None)
b.cooldowns.clear()
sig = b.evaluate_signal("BTC/USDT", base_data(atr_pct90=0.20))
check("atr_pct90 0.20 (lower edge) -> signal", sig is not None)
b.cooldowns.clear()
sig = b.evaluate_signal("BTC/USDT", base_data(atr_pct90=0.80))
check("atr_pct90 0.80 (upper edge) -> signal", sig is not None)
b.cooldowns.clear()
sig = b.evaluate_signal("BTC/USDT", base_data(atr_pct90=0.19))
check("atr_pct90 0.19 (compressed) -> blocked", sig is None)
b.cooldowns.clear()
sig = b.evaluate_signal("BTC/USDT", base_data(atr_pct90=0.81))
check("atr_pct90 0.81 (extreme vol) -> blocked", sig is None)
b.cooldowns.clear()
sig = b.evaluate_signal("BTC/USDT", base_data(atr_pct90=None))
check("atr_pct90 None (unknown) -> fail-open, signal", sig is not None)

print("== 2. 50DMA filter is optional / off by default ==")
check("V32_USE_50DMA is False by default", b.V32_USE_50DMA is False)
check("V31_REGIME_FILTER follows V32_USE_50DMA",
      b.V31_REGIME_FILTER is False)
b.cooldowns.clear()
# LONG while BTC is bearish (regime-against): 50DMA filter off, so the
# ATR gate alone decides. atr_pct90 in band -> signal allowed.
sig = b.evaluate_signal("BTC/USDT", base_data(regime_bullish=False,
                                               atr_pct90=0.50))
check("regime-against LONG passes when 50DMA filter off", sig is not None)
# Re-enable the 50DMA filter and confirm it blocks a regime-against trade.
b.V31_REGIME_FILTER = True
b.cooldowns.clear()
sig = b.evaluate_signal("BTC/USDT", base_data(regime_bullish=False,
                                               atr_pct90=0.50))
check("regime-against LONG blocked when 50DMA filter on", sig is None)
b.V31_REGIME_FILTER = False

print("== 3. Funding / partial-TP are off by default ==")
check("V32_FUNDING_FILTER is False (tested, not adopted)",
      b.V32_FUNDING_FILTER is False)
check("V32_PARTIAL_TP_R is 0.0 (tested, not adopted)",
      b.V32_PARTIAL_TP_R == 0.0)
check("V32_ATR_REGIME is True", b.V32_ATR_REGIME is True)
check("ATR band is [0.20, 0.80]",
      b.V32_ATR_LO == 0.20 and b.V32_ATR_HI == 0.80)

print("== 4. get_btc_atr_pct matches the backtest on local BTC daily ==")
klines_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "channel-analysis", "klines", "BTCUSDT_1d.json")
rows = json.load(open(klines_path))


class FakeExchange:
    def fetch_ohlcv(self, symbol, timeframe="1d", limit=150):
        return rows[-limit:]


real_exchange = b.exchange
b.exchange = FakeExchange()
b._atr_pct_cache = {"ts": None, "pct": None}
pct = b.get_btc_atr_pct()
b.exchange = real_exchange
check("get_btc_atr_pct returns a float in [0, 1]",
      pct is not None and 0.0 <= pct <= 1.0)
# Cross-check against the backtest's stored atr_pct90 for the same (latest)
# daily candle. Note: regime_v2_at() returns the last COMPLETED candle
# BEFORE a timestamp, so passing the last candle's own 00:00 would return
# the previous day -- compare the stored column directly instead.
import backtest_v3_2 as b2
import backtest_improvements as b1
btc_feat = b2.btc_daily_features()
row = btc_feat[btc_feat["ts"] == rows[-1][0]]
if not row.empty and row["atr_pct90"].iloc[0] is not None:
    exp_pct = float(row["atr_pct90"].iloc[0])
    last_ts = datetime.fromtimestamp(rows[-1][0] / 1000.0).strftime("%Y-%m-%d")
    check(f"bot pct {pct:.3f} matches backtest {exp_pct:.3f} on {last_ts}",
          abs(pct - exp_pct) < 0.01)
else:
    print("  SKIP: backtest has no atr_pct90 for the last date")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
