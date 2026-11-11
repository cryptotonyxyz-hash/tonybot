"""Backtest the TonyBot V3.0 -> V3.1 improvement plan against the recorded
channel history (1,096 V3.0 signals, 1,015 matched outcomes).

Baseline (original V3.0, from analyse_performance.py): 1,015 matched trades,
42.4% win rate, +0.018 R per trade, ~100-194 signals/month Mar-Oct.

Improvements tested (each alone, then combined):
  1. Regime filter: only trade with the macro BTC trend. BTC daily close vs
     its 50-day moving average, using the last COMPLETED daily candle before
     the signal (no look-ahead). LONG only when BTC > 50DMA, SHORT only when
     BTC < 50DMA.
  2. Tighten entry: (a) ADX rising (ADX now > ADX one 4H candle earlier),
     (b) ADX >= 30 instead of 25. Both use a consistently recomputed 4H
     ADX(14) series (see ADX note below). (c) Post-loss cooldown: after a
     taken trade closes as a loss, skip new signals for N hours.
  3. Drop NEAR and UNI; top-6 pairs only (LINK, SOL, LTC, ETH, XRP, BTC).
  4. Label: test whether ADX >= 50 + regime alignment separates winners
     from losers (a candidate new PREMIUM rule).
  5. Time-stop improvements (need 4H price paths from channel-analysis/
     klines/): (a) trailing stop to breakeven once the trade reaches +0.8R;
     (b) early exit at 12h if the trade is still red.
  6. Combined: all of the above together.

ADX NOTE: the ADX values printed in the channel's signal alerts were
reproduced almost exactly by ADX(14) computed on 60-MINUTE candles
(pandas_ta; BTC n=164 median abs diff 0.8, ETH n=110 median abs diff 1.0;
validated across all pairs in the 60m validation step). 4H ADX(14) did
NOT match (median abs diff ~9-10) and neither did 15m. So the original
bot's ADX is a 1H ADX, even though the trend filter uses 4H and 15M
EMA50s. The "ADX rising" test below therefore uses the 60m ADX(14)
series (now vs one 60m candle earlier), which is the bot's own series.
The rebuild's bot.py computes ADX from 4H candles -- that is a fidelity
bug in the rebuild, corrected in bot_v3_1.py.

TON: MEXC delisted TONUSDT (klines endpoint returns "Invalid symbol") and
Binance/OKX fallbacks are blocked/unavailable from this sandbox, so TON has
no 4H klines. TON is included in the non-kline tests but EXCLUDED from the
ADX-rising and time-stop tests (22 signals, 2.0% of the total).

APPROXIMATIONS in the time-stop simulation (4H granularity):
- The walk starts from the candle AFTER the entry candle (the entry candle's
  high/low may pre-date the signal, so it is excluded to avoid look-ahead).
- The 12h price is the close of the 4H candle containing the 12h mark.
- A breakeven exit is assumed at exactly 0R (no slippage/fees).
- For STOP_HIT trades that reached +0.8R first: price must cross the entry
  (breakeven stop) to reach the SL, so the trade is scored 0R (no-gap
  assumption). For TARGET_HIT trades, the trailing stop only fires if a full
  candle before the outcome candle touched the entry after arming.
- R is computed as pnl_pct / (sl_dist_pct * 10), as in analyse_performance.py.

Usage: /tmp/tonybot-test-venv/bin/python backtest_improvements.py
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import pandas_ta as ta

BASE = os.path.dirname(os.path.abspath(__file__))
KL = os.path.join(BASE, "channel-analysis", "klines")

TOP6 = {"LINK/USDT", "SOL/USDT", "LTC/USDT", "ETH/USDT", "XRP/USDT", "BTC/USDT"}
DROP_PAIRS = {"NEAR/USDT", "UNI/USDT"}


# ---------------------------------------------------------------- data load
def load_matched():
    with open(os.path.join(BASE, "channel-analysis", "signals.json")) as f:
        sigs = json.load(f)
    with open(os.path.join(BASE, "channel-analysis", "outcomes.json")) as f:
        outs = json.load(f)
    v3 = [o for o in outs if o["kind"] in ("TARGET_HIT", "STOP_HIT", "TIME_STOP")]
    sig_by_key = {(s["symbol"], round(s["entry"], 4)): s for s in sigs}
    matched = []
    for o in v3:
        if o.get("entry") is None:
            continue
        s = sig_by_key.get((o["symbol"], round(o["entry"], 4)))
        if not s:
            continue
        if o.get("pnl_pct") is None or not s.get("sl_dist_pct"):
            continue
        r = o["pnl_pct"] / (s["sl_dist_pct"] * 10.0)
        matched.append({"sig": s, "out": o, "r": r})
    matched.sort(key=lambda m: m["sig"]["ts"])
    return sigs, matched


def load_klines_4h():
    kl = {}
    for f in os.listdir(KL):
        if f.endswith("_4h.json"):
            sym = f.replace("_4h.json", "")
            rows = json.load(open(os.path.join(KL, f)))
            kl[sym] = rows
    return kl


def load_klines_60m():
    kl = {}
    for f in os.listdir(KL):
        if f.endswith("_60m.json"):
            sym = f.replace("_60m.json", "")
            rows = json.load(open(os.path.join(KL, f)))
            if rows:
                kl[sym] = rows
    return kl


def load_btc_daily():
    rows = json.load(open(os.path.join(KL, "BTCUSDT_1d.json")))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["ma50"] = df["close"].rolling(50).mean()
    return df


# ---------------------------------------------------------------- metrics
def metrics(rows, label):
    if not rows:
        return {"label": label, "n": 0, "wr": None, "avg_r": None}
    n = len(rows)
    w = sum(1 for m in rows if m["out"]["win"])
    avg_r = sum(m["r"] for m in rows) / n
    return {"label": label, "n": n, "wr": w / n, "avg_r": avg_r}


def show(m):
    if m["n"] == 0:
        print(f"  {m['label']}: n=0")
        return
    print(f"  {m['label']}: n={m['n']:4d}  win rate {m['wr']*100:5.1f}%  "
          f"avg {m['avg_r']:+.3f} R/trade")


def sigs_per_month(rows):
    c = Counter(m["sig"]["ts"][:7] for m in rows)
    vals = [c[m] for m in sorted(c)]
    return vals, (sum(vals) / len(vals) if vals else 0)


# ---------------------------------------------------------------- regime
def regime_bullish(btc_daily, ts_iso):
    """True if BTC's last completed daily close is above its 50DMA.
    No look-ahead: only daily candles that closed before ts_iso are used."""
    ts = pd.Timestamp(ts_iso, tz="UTC")
    past = btc_daily[btc_daily["ts"] <= ts]
    if past.empty or pd.isna(past.iloc[-1]["ma50"]):
        return None
    row = past.iloc[-1]
    return bool(row["close"] > row["ma50"])


def regime_aligned(btc_daily, m):
    bull = regime_bullish(btc_daily, m["sig"]["ts"])
    if bull is None:
        return None
    return (bull and m["sig"]["type"] == "LONG") or (
        not bull and m["sig"]["type"] == "SHORT")


# ---------------------------------------------------------------- ADX series
def adx_series_4h(kl_rows):
    """Return (timestamps_ms, adx_values) for 4H ADX(14) via pandas_ta."""
    df = pd.DataFrame(kl_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    a = ta.adx(df["high"], df["low"], df["close"], length=14)
    return df["ts"].tolist(), a["ADX_14"].tolist()


def adx_now_prev(kl_rows, ts_iso):
    """ADX(14) at the last 4H candle closing at/before ts, and the one before.
    Returns (adx_now, adx_prev) or (None, None)."""
    ts_ms = int(datetime.fromisoformat(ts_iso).replace(tzinfo=timezone.utc).timestamp() * 1000)
    sub = [r for r in kl_rows if r[0] <= ts_ms]
    if len(sub) < 40:
        return None, None
    df = pd.DataFrame(sub, columns=["ts", "open", "high", "low", "close", "volume"])
    a = ta.adx(df["high"], df["low"], df["close"], length=14)
    vals = a["ADX_14"].tolist()
    if len(vals) < 2 or pd.isna(vals[-1]) or pd.isna(vals[-2]):
        return None, None
    return float(vals[-1]), float(vals[-2])


# ---------------------------------------------------------------- time-stop sim
def simulate_time_stop(sig, out, candles, use_trail=True, use_early=True):
    """Simulate the improved time-stop for one matched trade.
    Returns the improved R (or the original R if unchanged).
    candles: list of [ts_ms, open, high, low, close, volume] for the pair.
    """
    entry = sig["entry"]
    stop = sig["stop"]
    sl_dist = abs(entry - stop)
    if sl_dist <= 0:
        return out_r(sig, out)
    is_long = sig["type"] == "LONG"
    lvl = entry + 0.8 * sl_dist if is_long else entry - 0.8 * sl_dist

    sig_ms = int(datetime.fromisoformat(sig["ts"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
    out_ms = int(datetime.fromisoformat(out["ts"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
    orig_r = out_r(sig, out)

    # Candle containing the signal (entry candle) and the outcome candle.
    # Walk starts from the candle AFTER the entry candle (no look-ahead
    # inside the entry candle) and stops before the outcome candle.
    idx_entry = None
    idx_out = None
    for i, c in enumerate(candles):
        if c[0] <= sig_ms < c[0] + 4 * 3600 * 1000:
            idx_entry = i
        if c[0] <= out_ms < c[0] + 4 * 3600 * 1000:
            idx_out = i
    if idx_entry is None or idx_out is None:
        return orig_r
    # 12h mark candle index.
    idx_12h = None
    t12 = sig_ms + 12 * 3600 * 1000
    for i, c in enumerate(candles):
        if c[0] <= t12 < c[0] + 4 * 3600 * 1000:
            idx_12h = i
            break

    armed = False
    # Walk candles after the entry candle, before the outcome candle.
    for i in range(idx_entry + 1, idx_out):
        c = candles[i]
        _, _, high, low, close, _ = c[0], c[1], c[2], c[3], c[4], c[5]
        # 12h early exit check (only if the trade is still open at 12h).
        if use_early and idx_12h is not None and i == idx_12h:
            r12 = (close - entry) / sl_dist if is_long else (entry - close) / sl_dist
            if r12 < 0:
                return r12
        if use_trail:
            if not armed:
                if (is_long and high >= lvl) or (not is_long and low <= lvl):
                    armed = True
            else:
                if (is_long and low <= entry) or (not is_long and high >= entry):
                    return 0.0
    # Outcome candle: for STOP_HIT, if armed the price must cross the entry
    # (breakeven stop) to reach the SL, so the trade exits at 0R.
    if use_trail and armed and out["kind"] == "STOP_HIT":
        return 0.0
    # 12h exit when the outcome is after 12h but the 12h candle is the
    # outcome candle itself (or the walk had no candle at 12h).
    if use_early and out_ms - sig_ms > 12 * 3600 * 1000 and idx_12h is not None:
        if idx_12h >= idx_out:
            c = candles[idx_12h]
            close = c[4]
            r12 = (close - entry) / sl_dist if is_long else (entry - close) / sl_dist
            if r12 < 0:
                return r12
    return orig_r


def out_r(sig, out):
    return out["pnl_pct"] / (sig["sl_dist_pct"] * 10.0)


# ---------------------------------------------------------------- cooldown sim
def apply_cooldown(rows, hours):
    """Sequential simulation: after a taken trade closes as a loss, skip
    signals for `hours`. The blackout starts at the loss's CLOSE time
    (out_ts), because that is when the bot learns the trade lost -- signals
    that arrived while the losing trade was still open were taken normally.
    No look-ahead: a signal is only skipped if its ts falls inside
    [out_ts, out_ts + hours) of an already-closed losing trade."""
    if hours <= 0:
        return list(rows)
    taken = []
    for m in rows:
        ts = datetime.fromisoformat(m["sig"]["ts"])
        blocked = False
        for t in taken:
            if t["out"]["win"]:
                continue
            out_ts = datetime.fromisoformat(t["out"]["ts"])
            if out_ts <= ts < out_ts + timedelta(hours=hours):
                blocked = True
                break
        if blocked:
            continue
        taken.append(m)
    return taken


# ---------------------------------------------------------------- main
def main():
    sigs, matched = load_matched()
    kl = load_klines_4h()
    btc_daily = load_btc_daily()
    print(f"Matched V3.0 trades: {len(matched)} (of 1,096 signals)")
    print(f"4H klines loaded for {len(kl)} pairs "
          f"(TON missing: MEXC delisted TONUSDT)")

    out_lines = []

    def header(t):
        print(f"\n========== {t} ==========")
        out_lines.append(f"\n========== {t} ==========")

    def report(m):
        show(m)
        if m["n"]:
            out_lines.append(
                f"  {m['label']}: n={m['n']}  win rate {m['wr']*100:.1f}%  "
                f"avg {m['avg_r']:+.3f} R/trade")

    # ---- 0. Baseline ----
    header("0. BASELINE (original V3.0, all matched trades)")
    base = metrics(matched, "baseline")
    report(base)
    months, avg_pm = sigs_per_month(matched)
    print(f"  Signals/month (matched): {months}  avg {avg_pm:.0f}/month")
    out_lines.append(f"  Signals/month (matched): avg {avg_pm:.0f}/month")

    # ---- 1. Regime filter ----
    header("1. REGIME FILTER (BTC vs 50DMA, no look-ahead)")
    aligned = [m for m in matched if regime_aligned(btc_daily, m) is True]
    against = [m for m in matched if regime_aligned(btc_daily, m) is False]
    unknown = [m for m in matched if regime_aligned(btc_daily, m) is None]
    report(metrics(aligned, "regime-aligned only"))
    report(metrics(against, "regime-against only (would be skipped)"))
    print(f"  Regime unknown (no 50DMA yet): n={len(unknown)}")
    out_lines.append(f"  Regime unknown (no 50DMA yet): n={len(unknown)}")
    # Direction x regime breakdown
    for d in ("LONG", "SHORT"):
        for al in (True, False):
            rows = [m for m in matched
                    if m["sig"]["type"] == d and regime_aligned(btc_daily, m) is al]
            report(metrics(rows, f"{d} regime-aligned={al}"))
    months, avg_pm = sigs_per_month(aligned)
    print(f"  Regime-aligned signals/month: avg {avg_pm:.0f}/month")
    out_lines.append(f"  Regime-aligned signals/month: avg {avg_pm:.0f}/month")

    # ---- 2a. ADX rising (60m ADX = the bot's own series) ----
    header("2a. ADX RISING (60m ADX(14), now > prev 60m candle)")
    kl60 = load_klines_60m()
    print(f"  60m klines loaded for {len(kl60)} pairs (TON missing)")
    rising, falling, noadx = [], [], []
    for m in matched:
        sym = m["sig"]["symbol"].replace("/", "")
        rows = kl60.get(sym)
        if rows is None:
            noadx.append(m)
            continue
        now, prev = adx_now_prev(rows, m["sig"]["ts"])
        if now is None:
            noadx.append(m)
        elif now > prev:
            rising.append(m)
        else:
            falling.append(m)
    report(metrics(rising, "ADX rising"))
    report(metrics(falling, "ADX flat/falling (would be skipped)"))
    print(f"  No ADX data (TON): n={len(noadx)}")
    out_lines.append(f"  No ADX data (TON): n={len(noadx)}")

    header("2b. ADX >= 30 (instead of >= 25)")
    hi = [m for m in matched if m["sig"]["adx"] is not None and m["sig"]["adx"] >= 30]
    lo = [m for m in matched if m["sig"]["adx"] is not None and m["sig"]["adx"] < 30]
    report(metrics(hi, "ADX >= 30"))
    report(metrics(lo, "ADX 25-30 (would be skipped)"))

    # ---- 2c. Post-loss cooldown ----
    header("2c. POST-LOSS COOLDOWN (sequential, no look-ahead)")
    for hrs in (12, 24):
        taken = apply_cooldown(matched, hrs)
        report(metrics(taken, f"cooldown {hrs}h after a loss"))
        months, avg_pm = sigs_per_month(taken)
        print(f"    signals/month: avg {avg_pm:.0f}/month")
        out_lines.append(f"    cooldown {hrs}h signals/month: avg {avg_pm:.0f}/month")

    # ---- 3. Pair filter ----
    header("3. PAIR FILTER (drop NEAR + UNI; top-6 only)")
    top6 = [m for m in matched if m["sig"]["symbol"] in TOP6]
    rest = [m for m in matched if m["sig"]["symbol"] not in TOP6]
    dropped = [m for m in matched if m["sig"]["symbol"] in DROP_PAIRS]
    report(metrics(top6, "top-6 pairs only"))
    report(metrics(rest, "other 9 pairs (would be skipped)"))
    report(metrics(dropped, "NEAR+UNI only (would be dropped)"))
    months, avg_pm = sigs_per_month(top6)
    print(f"  Top-6 signals/month: avg {avg_pm:.0f}/month")
    out_lines.append(f"  Top-6 signals/month: avg {avg_pm:.0f}/month")

    # ---- 4. Label ----
    header("4. LABEL: does ADX>=50 + regime alignment separate winners?")
    for name, pred in [
        ("ADX >= 50", lambda m: m["sig"]["adx"] is not None and m["sig"]["adx"] >= 50),
        ("ADX >= 50 AND regime-aligned",
         lambda m: m["sig"]["adx"] is not None and m["sig"]["adx"] >= 50
         and regime_aligned(btc_daily, m) is True),
        ("ADX >= 40 AND regime-aligned",
         lambda m: m["sig"]["adx"] is not None and m["sig"]["adx"] >= 40
         and regime_aligned(btc_daily, m) is True),
    ]:
        yes = [m for m in matched if pred(m)]
        no = [m for m in matched if not pred(m)]
        report(metrics(yes, f"candidate PREMIUM: {name}"))
        report(metrics(no, f"candidate HIGH: not ({name})"))

    # ---- 5. Time-stop improvements ----
    header("5. TIME-STOP IMPROVEMENTS (4H price paths; TON excluded)")
    kline_rows = []
    for m in matched:
        sym = m["sig"]["symbol"].replace("/", "")
        if sym in kl:
            kline_rows.append(m)
    print(f"  Trades with 4H price data: n={len(kline_rows)} "
          f"(excluded TON n={len(matched) - len(kline_rows)})")
    out_lines.append(f"  Trades with 4H price data: n={len(kline_rows)} "
                     f"(excluded TON n={len(matched) - len(kline_rows)})")

    def with_sim(rows, use_trail, use_early, label):
        new_rows = []
        for m in rows:
            sym = m["sig"]["symbol"].replace("/", "")
            r2 = simulate_time_stop(m["sig"], m["out"], kl[sym],
                                    use_trail=use_trail, use_early=use_early)
            m2 = dict(m)
            m2["r"] = r2
            new_rows.append(m2)
        return metrics(new_rows, label)

    report(with_sim(kline_rows, True, False, "trailing stop to BE at +0.8R"))
    report(with_sim(kline_rows, False, True, "12h early exit if red"))
    report(with_sim(kline_rows, True, True, "trailing BE + 12h early exit"))
    # How many trades changed?
    changed = 0
    for m in kline_rows:
        sym = m["sig"]["symbol"].replace("/", "")
        r2 = simulate_time_stop(m["sig"], m["out"], kl[sym], True, True)
        if abs(r2 - m["r"]) > 1e-9:
            changed += 1
    print(f"  Trades whose outcome changed under both improvements: {changed}/{len(kline_rows)}")
    out_lines.append(f"  Trades whose outcome changed under both improvements: {changed}/{len(kline_rows)}")

    # ---- 6. Combinations ----
    header("6. COMBINATIONS (selection filters; 60m ADX for rising)")
    kl60 = load_klines_60m()

    def adx_rising_60m(m):
        sym = m["sig"]["symbol"].replace("/", "")
        rows = kl60.get(sym)
        if rows is None:
            return None
        now, prev = adx_now_prev(rows, m["sig"]["ts"])
        if now is None:
            return None
        return now > prev

    def combo(rows, label):
        mm = metrics(rows, label)
        report(mm)
        _, avg_pm = sigs_per_month(rows)
        print(f"    signals/month: avg {avg_pm:.0f}/month")
        out_lines.append(f"    {label} signals/month: avg {avg_pm:.0f}/month")
        return mm

    reg = [m for m in matched if regime_aligned(btc_daily, m) is True]
    top6 = [m for m in matched if m["sig"]["symbol"] in TOP6]
    rising = [m for m in matched if adx_rising_60m(m) is True]
    combo(reg, "regime only")
    combo(top6, "top-6 only")
    combo(rising, "ADX rising (60m) only")
    combo([m for m in reg if m["sig"]["symbol"] in TOP6], "regime + top-6")
    combo([m for m in reg if adx_rising_60m(m) is True], "regime + ADX rising")
    combo([m for m in top6 if adx_rising_60m(m) is True], "top-6 + ADX rising")
    reg_top6_rising = [m for m in reg
                       if m["sig"]["symbol"] in TOP6
                       and adx_rising_60m(m) is True]
    combo(reg_top6_rising, "regime + top-6 + ADX rising")
    # Cooldowns on the mild three-filter combination.
    for hrs in (12, 24):
        combo(apply_cooldown(reg_top6_rising, hrs),
              f"regime + top-6 + ADX rising + {hrs}h cooldown")

    # ---- Full V3.1: selection + time-stop improvements ----
    header("6b. FULL V3.1 (selection + trailing BE + 12h early exit)")
    sel3 = apply_cooldown(reg_top6_rising, 12)
    print(f"  Selection (regime+top6+ADX rising+12h cooldown): n={len(sel3)}")
    out_lines.append(f"  Selection (regime+top6+ADX rising+12h cooldown): n={len(sel3)}")
    final_rows = []
    for m in sel3:
        sym = m["sig"]["symbol"].replace("/", "")
        r2 = simulate_time_stop(m["sig"], m["out"], kl[sym], True, True)
        m2 = dict(m)
        m2["r"] = r2
        final_rows.append(m2)
    report(metrics(final_rows, "FULL V3.1 (with time-stop changes)"))
    months, avg_pm = sigs_per_month(final_rows)
    print(f"  Full V3.1 signals/month: {months}  avg {avg_pm:.0f}/month")
    out_lines.append(f"  Full V3.1 signals/month: {months}  avg {avg_pm:.0f}/month")
    # Same selection WITHOUT the time-stop improvements, for attribution.
    report(metrics(sel3, "selection only (no time-stop changes)"))
    # Win rate by month for the combined version.
    print("\n  Combined win rate by month:")
    out_lines.append("\n  Combined win rate by month:")
    by_month = defaultdict(list)
    for m in final_rows:
        by_month[m["sig"]["ts"][:7]].append(m)
    for mo in sorted(by_month):
        mm = metrics(by_month[mo], mo)
        print(f"    {mo}: {mm['wr']*100:5.1f}%  (n={mm['n']})  avg {mm['avg_r']:+.3f} R")
        out_lines.append(f"    {mo}: {mm['wr']*100:.1f}%  (n={mm['n']})  avg {mm['avg_r']:+.3f} R")

    # ---- Summary vs baseline ----
    header("SUMMARY vs BASELINE")
    b = base
    f = metrics(final_rows, "combined")
    print(f"  Baseline : n={b['n']}  win {b['wr']*100:.1f}%  avg {b['avg_r']:+.3f} R")
    print(f"  V3.1     : n={f['n']}  win {f['wr']*100:.1f}%  avg {f['avg_r']:+.3f} R")
    print(f"  Delta    : avg R {f['avg_r'] - b['avg_r']:+.3f} R/trade, "
          f"win rate {(f['wr'] - b['wr'])*100:+.1f} pts, "
          f"trades {f['n'] - b['n']:+d}")
    out_lines.append(f"  Baseline : n={b['n']}  win {b['wr']*100:.1f}%  avg {b['avg_r']:+.3f} R")
    out_lines.append(f"  V3.1     : n={f['n']}  win {f['wr']*100:.1f}%  avg {f['avg_r']:+.3f} R")
    out_lines.append(f"  Delta    : avg R {f['avg_r'] - b['avg_r']:+.3f} R/trade, "
                     f"win rate {(f['wr'] - b['wr'])*100:+.1f} pts, "
                     f"trades {f['n'] - b['n']:+d}")

    with open(os.path.join(BASE, "channel-analysis", "improvements-report.txt"), "w") as fh:
        fh.write("TonyBot V3.0 -> V3.1 improvement backtest\n")
        fh.write("Matched V3.0 trades: %d (of 1,096 signals)\n" % len(matched))
        fh.write("Method, approximations and caveats: see backtest_improvements.py header.\n")
        fh.write("\n".join(out_lines))
        fh.write("\n")
    print("\nWrote channel-analysis/improvements-report.txt")


if __name__ == "__main__":
    main()
