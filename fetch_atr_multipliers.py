"""Determine the SL multiplier (SL distance / ATR) for the original bot by
fetching historical 4H klines from MEXC for a sample of real signals and
computing ATR(14) with pandas_ta at each signal's entry time.

The channel export's signal alerts carry entry/stop but no ATR, so the
multiplier cannot be read off directly. This script:
  1. Loads channel-analysis/signals.json.
  2. Samples N signals spread across pairs and months.
  3. For each, fetches 4H klines ending at the signal time from MEXC
     (public REST, no ccxt load_markets — the sandbox blocks that call).
  4. Computes ATR(14) and the implied multiplier = SL distance % / ATR %.
Usage: python fetch_atr_multipliers.py [N]  (default 30)
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd


def atr14_pct(df):
    """ATR(14) as % of the last close, Wilder's smoothing (pure pandas).
    Matches pandas_ta's ATR(14); used here so no pandas_ta install is
    needed for this one-off analysis."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / 14, adjust=False, min_periods=14).mean()
    last_atr = float(atr.iloc[-1])
    last_close = float(close.iloc[-1])
    if last_close == 0:
        return None
    return last_atr / last_close * 100

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def klines_4h(symbol, end_ms, limit=200):
    """Fetch 4H klines ending at end_ms (inclusive) from MEXC.
    NOTE: MEXC ignores endTime (and startTime) when passed alone; both
    must be given together. So we set startTime = end - limit*4h."""
    sym = symbol.replace("/", "")
    start_ms = end_ms - limit * 4 * 3600 * 1000
    url = (f"https://api.mexc.com/api/v3/klines?symbol={sym}"
           f"&interval=4h&limit={limit}&startTime={start_ms}&endTime={end_ms}")
    req = urllib.request.Request(url, headers={"User-Agent": "tonybot-rebuild"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = json.loads(r.read())
    return [[k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]),
             float(k[5])] for k in raw]


def atr_pct_at(symbol, ts_iso):
    """ATR(14) as % of close for the 4H candle closing at/before ts_iso."""
    dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    end_ms = int(dt.timestamp() * 1000)
    kl = klines_4h(symbol, end_ms)
    if len(kl) < 60:
        return None
    df = pd.DataFrame(kl, columns=["ts", "open", "high", "low", "close",
                                   "volume"])
    return atr14_pct(df)


def main():
    with open("channel-analysis/signals.json") as f:
        sigs = json.load(f)
    # Spread the sample across pairs and time: sort by ts, take evenly.
    sigs = sorted(sigs, key=lambda s: s["ts"])
    step = max(1, len(sigs) // N)
    sample = sigs[::step][:N]
    print(f"Sampling {len(sample)} of {len(sigs)} signals")
    results = []
    for s in sample:
        if not s.get("entry") or not s.get("stop"):
            continue
        sl_pct = abs(s["entry"] - s["stop"]) / s["entry"] * 100
        try:
            atrp = atr_pct_at(s["symbol"], s["ts"])
        except Exception as e:
            print(f"  {s['symbol']} {s['ts']}: fetch failed ({e})")
            continue
        if atrp is None:
            print(f"  {s['symbol']} {s['ts']}: no ATR")
            continue
        mult = sl_pct / atrp
        results.append({"symbol": s["symbol"], "ts": s["ts"],
                        "type": s["type"], "sl_pct": round(sl_pct, 3),
                        "atr_pct": round(atrp, 3),
                        "multiplier": round(mult, 3)})
        print(f"  {s['symbol']} {s['ts'][:10]} {s['type']:5s} "
              f"SL {sl_pct:.2f}% / ATR {atrp:.2f}% = x{mult:.2f}")
        time.sleep(0.3)
    if not results:
        print("No results.")
        return
    mults = sorted(r["multiplier"] for r in results)
    n = len(mults)
    print(f"\nMultiplier: n={n}, min={mults[0]:.2f}, "
          f"median={mults[n//2]:.2f}, mean={sum(mults)/n:.2f}, "
          f"max={mults[-1]:.2f}")
    with open("channel-analysis/atr_multipliers.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Wrote channel-analysis/atr_multipliers.json")


if __name__ == "__main__":
    main()
