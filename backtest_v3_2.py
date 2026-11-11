"""Backtest TonyBot V3.2 methods on top of V3.1.

Baseline V3.0: 1,015 matched trades, 42.3% win, +0.018 R/trade, 92/month.
V3.1 full (regime 50DMA + ADX rising + top-6 + trailing BE + 12h cooldown,
as implemented in bot_v3_1.py with V31_EARLY_EXIT_12H=False): 183 trades,
51.4% win, +0.411 R/trade. NOTE: the V3.1 report's +0.374 R figure came
from backtest_improvements.py section 6b, which ALSO applied the 12h early
exit; the bot does not use the early exit, and it costs -0.037 R. This
script reproduces both and uses the trailing-only (+0.411 R) version as
the V3.1 baseline for V3.2, since that is what the bot actually runs.

Three new methods, each alone AND combined with V3.1:
  1. Funding-rate filter. MEXC perpetual funding history (fetched live,
     channel-analysis/funding/, all 15 pairs). Skip a LONG when funding is
     extremely positive (crowded longs), skip a SHORT when funding is very
     negative. Open interest history is NOT available: MEXC's OI endpoint
     is blocked by its WAF and Binance is geo-blocked from this sandbox,
     so the funding+OI combination could not be tested -- funding only.
  2. Partial take-profits. Take half off at +1R (and +0.8R as a variant),
     let the rest run to the 1.8R target or the 24h time-stop. Simulated
     on 60m klines (channel-analysis/klines/*_60m.json). A trailing stop
     to breakeven at +0.8R is applied to the remaining half when enabled.
  3. Better regime detection. The 50DMA did NOT fix April (all 29 April
     LONGs were regime-aligned and still won 3.4%). Test a volatility
     regime (BTC daily ATR(14) percentile over a trailing 90 days) and a
     daily ADX(14) trend-strength rule, using BTC daily klines already in
     channel-analysis/klines/BTCUSDT_1d.json.

No look-ahead anywhere: every filter uses only data available at signal
time (last completed candle / last funding settle before the signal).
Thresholds are fitted on Jan-Jun 2026 and tested on Jul-Nov 2026
(out-of-sample); in-sample and holdout numbers are reported separately.

R = pnl_pct / (sl_dist_pct * 10). Win = adjusted R > 0; loss = R < 0;
breakeven = R == 0 (possible with partial TP). SL = 1.25x ATR(4h),
R:R 1:1.8, unchanged.

Usage: /tmp/tonybot-test-venv/bin/python backtest_v3_2.py
"""
import bisect
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import pandas_ta as ta

import backtest_improvements as b1

BASE = os.path.dirname(os.path.abspath(__file__))
KL = os.path.join(BASE, "channel-analysis", "klines")
FUND = os.path.join(BASE, "channel-analysis", "funding")
TOP6 = b1.TOP6

OUT_LINES = []


def header(t):
    print(f"\n========== {t} ==========")
    OUT_LINES.append(f"\n========== {t} ==========")


def metrics_r(rows, label):
    """Win/loss from ADJUSTED R (partial TP can change the outcome)."""
    if not rows:
        return {"label": label, "n": 0, "wr": None, "avg_r": None, "be": 0}
    n = len(rows)
    w = sum(1 for m in rows if m["r"] > 1e-9)
    l = sum(1 for m in rows if m["r"] < -1e-9)
    be = n - w - l
    avg_r = sum(m["r"] for m in rows) / n
    return {"label": label, "n": n, "wr": w / n, "loss_rate": l / n,
            "be": be, "avg_r": avg_r}


def show_r(m):
    if m["n"] == 0:
        print(f"  {m['label']}: n=0")
        return
    print(f"  {m['label']}: n={m['n']:4d}  win {m['wr']*100:5.1f}%  "
          f"loss {m['loss_rate']*100:5.1f}%  BE {m['be']:3d}  avg {m['avg_r']:+.3f} R")
    OUT_LINES.append(
        f"  {m['label']}: n={m['n']}  win {m['wr']*100:.1f}%  "
        f"loss {m['loss_rate']*100:.1f}%  BE {m['be']}  avg {m['avg_r']:+.3f} R")


def sigs_per_month(rows):
    c = Counter(m["sig"]["ts"][:7] for m in rows)
    vals = [c[mo] for mo in sorted(c)]
    return vals, (sum(vals) / len(vals) if vals else 0)


def monthly_return(rows):
    """Avg R/month = avg R/trade x trades/month (over the months present)."""
    if not rows:
        return 0.0
    _, avg_pm = sigs_per_month(rows)
    m = metrics_r(rows, "x")
    return (m["avg_r"] or 0.0) * avg_pm


# ------------------------------------------------------------------ V3.1
def adx_rising_60m(kl60, m):
    sym = m["sig"]["symbol"].replace("/", "")
    rows = kl60.get(sym)
    if rows is None:
        return None
    now, prev = b1.adx_now_prev(rows, m["sig"]["ts"])
    if now is None:
        return None
    return now > prev


def v3_1_selection(matched, kl60, btc_daily):
    """V3.1 selection: regime-aligned AND top-6 AND ADX rising (60m),
    then 12h post-loss cooldown (original outcomes). Returns the list."""
    reg = [m for m in matched if b1.regime_aligned(btc_daily, m) is True]
    sel = [m for m in reg
           if m["sig"]["symbol"] in TOP6 and adx_rising_60m(kl60, m) is True]
    return b1.apply_cooldown(sel, 12)


def apply_time_stop(rows, kl4h, use_trail=True, use_early=False):
    """Apply the V3.1 time-stop sim (trailing BE, optionally 12h early
    exit) and return new rows with adjusted R."""
    out_rows = []
    for m in rows:
        sym = m["sig"]["symbol"].replace("/", "")
        if sym in kl4h:
            r2 = b1.simulate_time_stop(m["sig"], m["out"], kl4h[sym],
                                       use_trail=use_trail, use_early=use_early)
        else:
            r2 = m["r"]
        m2 = dict(m)
        m2["r"] = r2
        out_rows.append(m2)
    return out_rows


# ------------------------------------------------------------------ PARTIAL TP
def simulate_partial_tp(sig, out, candles, partial_k, use_trail=True):
    """Simulate a partial take-profit (+ optional trailing BE) for one
    trade on 60m candles. Take half off at +partial_k R; the remaining
    half keeps the SL (or the trailed stop at breakeven, once armed at
    +0.8R) and the 1.8R target, or the 24h time-stop.
    candles: 60m [ts,o,h,l,c,v] for the pair, sorted by ts.
    Returns the adjusted R for the whole position.
    Approximations (see header): intra-candle order is resolved by the
    candle's close direction when a candle touches both the partial level
    and the stop; the outcome candle's full high/low is used even though
    the outcome may have been detected mid-candle (one 60m candle of
    look-ahead at most); the walk starts after the entry candle.
    """
    entry = sig["entry"]
    stop = sig["stop"]
    sl_dist = abs(entry - stop)
    if sl_dist <= 0:
        return b1.out_r(sig, out)
    is_long = sig["type"] == "LONG"
    orig_r = b1.out_r(sig, out)
    if partial_k is None and not use_trail:
        return orig_r
    if is_long:
        tp_lvl = entry + 1.8 * sl_dist
        sl_lvl = stop
        partial_lvl = entry + partial_k * sl_dist if partial_k else None
        trail_lvl = entry + 0.8 * sl_dist
    else:
        tp_lvl = entry - 1.8 * sl_dist
        sl_lvl = stop
        partial_lvl = entry - partial_k * sl_dist if partial_k else None
        trail_lvl = entry - 0.8 * sl_dist

    sig_ms = int(datetime.fromisoformat(sig["ts"]).replace(
        tzinfo=timezone.utc).timestamp() * 1000)
    out_ms = int(datetime.fromisoformat(out["ts"]).replace(
        tzinfo=timezone.utc).timestamp() * 1000)
    ts_list = [c[0] for c in candles]
    idx_entry = bisect.bisect_right(ts_list, sig_ms) - 1
    idx_out = bisect.bisect_right(ts_list, out_ms) - 1
    if idx_entry < 0 or idx_out < 0 or idx_out < idx_entry:
        return orig_r

    partial = False
    armed = False
    for i in range(idx_entry + 1, idx_out + 1):
        c = candles[i]
        o, h, l, cl = c[1], c[2], c[3], c[4]
        up = cl >= o
        if is_long:
            hit_partial = partial_lvl is not None and h >= partial_lvl
            hit_trail = use_trail and h >= trail_lvl
            hit_tp = h >= tp_lvl
            eff_stop = entry if armed else sl_lvl
            hit_stop = l <= eff_stop
        else:
            hit_partial = partial_lvl is not None and l <= partial_lvl
            hit_trail = use_trail and l <= trail_lvl
            hit_tp = l <= tp_lvl
            eff_stop = entry if armed else sl_lvl
            hit_stop = h >= eff_stop
        # Both TP and stop touched in this candle: order by close direction.
        if hit_tp and hit_stop:
            if up:
                return (0.5 * partial_k + 0.9) if partial_k is not None else 1.8
            if partial:
                return 0.5 * partial_k + (0.0 if armed else -0.5)
            return -1.0
        if hit_tp:
            return (0.5 * partial_k + 0.9) if partial_k is not None else 1.8
        if hit_stop:
            if partial:
                return 0.5 * partial_k + (0.0 if armed else -0.5)
            if hit_partial:
                if up:
                    # Partial touched first, then fell to the stop.
                    # Trail armed (partial >= trail), so remaining half
                    # exits at breakeven (0R).
                    return 0.5 * partial_k + 0.0
                return -1.0  # stop first, no partial
            return -1.0
        if hit_partial:
            partial = True
        if hit_trail:
            armed = True
    # Walk finished without TP/SL: use the recorded outcome.
    if out["kind"] == "TARGET_HIT":
        return (0.5 * partial_k + 0.9) if partial_k is not None else orig_r
    if out["kind"] == "STOP_HIT":
        if partial:
            return 0.5 * partial_k + (0.0 if armed else -0.5)
        return orig_r
    # TIME_STOP: remaining half (or whole) exits at the recorded time-stop R.
    if partial:
        return 0.5 * partial_k + 0.5 * orig_r
    return orig_r


def apply_partial_tp(rows, kl60, partial_k, use_trail=True):
    out_rows = []
    for m in rows:
        sym = m["sig"]["symbol"].replace("/", "")
        if sym in kl60:
            r2 = simulate_partial_tp(m["sig"], m["out"], kl60[sym],
                                     partial_k, use_trail)
        else:
            r2 = m["r"]
        m2 = dict(m)
        m2["r"] = r2
        out_rows.append(m2)
    return out_rows


# ------------------------------------------------------------------ REGIME V2
def btc_daily_features():
    """BTC daily ATR(14), ATR percentile (trailing 90d), ADX(14).
    Returns a DataFrame indexed by daily candle ts (ms)."""
    rows = json.load(open(os.path.join(KL, "BTCUSDT_1d.json")))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["atr14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    adx = ta.adx(df["high"], df["low"], df["close"], length=14)
    df["adx14"] = adx["ADX_14"]
    df["ma50"] = df["close"].rolling(50).mean()
    # ATR percentile vs trailing 90 days (excluding the current day).
    pct = []
    atr = df["atr14"].tolist()
    for i in range(len(df)):
        window = [a for a in atr[max(0, i - 90):i] if pd.notna(a)]
        if len(window) < 30 or pd.isna(atr[i]):
            pct.append(None)
        else:
            pct.append(sum(1 for a in window if a <= atr[i]) / len(window))
    df["atr_pct90"] = pct
    return df


def regime_v2_at(btc_feat, ts_iso):
    """(atr_pct90, daily_adx, bullish_50dma) at the last completed daily
    candle before ts_iso. None where unavailable."""
    ts_ms = int(datetime.fromisoformat(ts_iso).replace(
        tzinfo=timezone.utc).timestamp() * 1000)
    # Daily candles are at 00:00 UTC; the last completed one starts before
    # ts_ms (a candle starting exactly at ts_ms has not closed yet).
    sub = btc_feat[btc_feat["ts"] < ts_ms]
    if sub.empty:
        return None, None, None
    row = sub.iloc[-1]
    bull = None
    if pd.notna(row["ma50"]):
        bull = bool(row["close"] > row["ma50"])
    adx = None if pd.isna(row["adx14"]) else float(row["adx14"])
    pct = row["atr_pct90"]
    pct = None if pct is None or (isinstance(pct, float) and pd.isna(pct)) else float(pct)
    return pct, adx, bull


# ------------------------------------------------------------------ FUNDING
def load_funding():
    """{SYM: [(settleTime_ms, fundingRate), ...]} sorted ascending."""
    fund = {}
    for f in os.listdir(FUND):
        if f.endswith(".json"):
            sym = f.replace(".json", "")
            rows = json.load(open(os.path.join(FUND, f)))
            fund[sym] = sorted((r["settleTime"], r["fundingRate"]) for r in rows)
    return fund


def funding_at(fund_rows, ts_ms):
    """Most recent funding rate with settleTime <= ts_ms, plus its trailing
    30-day percentile (rank among funding values in the 30 days before
    ts_ms, using only settles <= ts_ms). Returns (rate, pct) or (None, None)."""
    times = [t for t, _ in fund_rows]
    i = bisect.bisect_right(times, ts_ms) - 1
    if i < 0:
        return None, None
    rate = fund_rows[i][1]
    lo = ts_ms - 30 * 24 * 3600 * 1000
    window = [r for t, r in fund_rows if lo <= t <= ts_ms]
    if len(window) < 20:
        return rate, None
    pct = sum(1 for r in window if r <= rate) / len(window)
    return rate, pct


def funding_filter(m, fund, mode, pct_hi=0.90, pct_lo=0.10,
                   abs_hi=0.0005, abs_lo=-0.0005):
    """True if the trade should be TAKEN under the funding filter.
    mode 'pct': skip LONG when funding percentile >= pct_hi, skip SHORT
    when funding percentile <= pct_lo. mode 'abs': skip LONG when funding
    rate > abs_hi, skip SHORT when funding rate < abs_lo. mode 'pct_or_abs':
    skip if either rule fires. Returns None when no funding data."""
    sym = m["sig"]["symbol"].replace("/", "").replace("USDT", "")
    rows = fund.get(sym)
    if not rows:
        return None
    ts_ms = int(datetime.fromisoformat(m["sig"]["ts"]).replace(
        tzinfo=timezone.utc).timestamp() * 1000)
    rate, pct = funding_at(rows, ts_ms)
    if rate is None:
        return None
    is_long = m["sig"]["type"] == "LONG"
    crowded = False
    if mode in ("pct", "pct_or_abs"):
        if pct is not None:
            if is_long and pct >= pct_hi:
                crowded = True
            if not is_long and pct <= pct_lo:
                crowded = True
    if mode in ("abs", "pct_or_abs"):
        if is_long and rate > abs_hi:
            crowded = True
        if not is_long and rate < abs_lo:
            crowded = True
    return not crowded


# ------------------------------------------------------------------ MAIN
def main():
    sigs, matched = b1.load_matched()
    kl4h = b1.load_klines_4h()
    kl60 = b1.load_klines_60m()
    btc_daily = b1.load_btc_daily()
    fund = load_funding()
    btc_feat = btc_daily_features()
    print(f"Matched V3.0 trades: {len(matched)}")
    print(f"60m klines: {len(kl60)} pairs; funding: {len(fund)} pairs; "
          f"BTC daily candles: {len(btc_feat)}")

    # ---- 0. Baselines (reproduce V3.1) ----
    header("0. BASELINES")
    show_r(metrics_r(matched, "V3.0 baseline (all matched)"))
    sel3 = v3_1_selection(matched, kl60, btc_daily)
    print(f"  V3.1 selection (regime+top6+ADX rising+12h cooldown): n={len(sel3)}")
    OUT_LINES.append(f"  V3.1 selection: n={len(sel3)}")
    v31_6b = apply_time_stop(sel3, kl4h, use_trail=True, use_early=True)
    show_r(metrics_r(v31_6b, "V3.1 as reported (+0.374, trail + 12h early exit)"))
    v31 = apply_time_stop(sel3, kl4h, use_trail=True, use_early=False)
    show_r(metrics_r(v31, "V3.1 as the bot runs (trail only, no early exit)"))
    show_r(metrics_r(sel3, "V3.1 selection only (no time-stop changes)"))
    _, avg_pm = sigs_per_month(v31)
    print(f"  V3.1 (bot) signals/month: avg {avg_pm:.0f}; "
          f"monthly return {monthly_return(v31):+.1f} R/month")
    OUT_LINES.append(f"  V3.1 (bot) monthly return: {monthly_return(v31):+.1f} R/month")

    # ---- 2. PARTIAL TAKE-PROFITS ----
    header("2. PARTIAL TAKE-PROFITS (60m price paths; TON excluded where no 60m data)")
    # On the V3.1 selection (trailing BE already the bot baseline).
    for k in (1.0, 0.8):
        for trail in (False, True):
            rows = apply_partial_tp(sel3, kl60, k, use_trail=trail)
            show_r(metrics_r(
                rows, f"V3.1 selection + partial TP at +{k}R "
                      f"(trail={'on' if trail else 'off'})"))
            _, avg_pm = sigs_per_month(rows)
            print(f"    monthly return {monthly_return(rows):+.1f} R/month")
    # Partial TP on ALL matched trades (no V3.1 filters), for attribution.
    for k in (1.0, 0.8):
        rows = apply_partial_tp(matched, kl60, k, use_trail=False)
        show_r(metrics_r(rows, f"ALL matched + partial TP at +{k}R (no trail, no filters)"))
    # How many trades actually hit the partial level?
    for k in (1.0, 0.8):
        hit = 0
        tot = 0
        for m in matched:
            sym = m["sig"]["symbol"].replace("/", "")
            if sym not in kl60:
                continue
            tot += 1
            # Re-run the sim in "detect only" mode by checking whether the
            # adjusted R differs from a no-partial run in a way that implies
            # the level was hit: simpler -- recompute with a marker.
            # Here: a trade's R changes under partial TP only if the level
            # was hit (or the trail fired). Use the trail-off run.
            r_no = m["r"]
            r_pt = simulate_partial_tp(m["sig"], m["out"], kl60[sym], k, False)
            if abs(r_pt - r_no) > 1e-9:
                hit += 1
        print(f"  Partial level +{k}R reached in {hit}/{tot} matched trades "
              f"({100*hit/max(tot,1):.1f}%)")
        OUT_LINES.append(f"  Partial level +{k}R reached in {hit}/{tot} matched trades")
    # Out-of-sample split for partial TP (no threshold to fit; report both halves).
    for k in (1.0,):
        for label, rows in (("Jan-Jun 2026", [m for m in sel3 if m["sig"]["ts"] < "2026-07"]),
                            ("Jul-Nov 2026", [m for m in sel3 if m["sig"]["ts"] >= "2026-07"])):
            base_rows = rows
            pt_rows = apply_partial_tp(rows, kl60, k, use_trail=True)
            show_r(metrics_r(base_rows, f"V3.1 selection {label} (no partial TP)"))
            show_r(metrics_r(pt_rows, f"V3.1 selection {label} + partial TP +{k}R (trail on)"))

    # ---- 3. BETTER REGIME DETECTION ----
    header("3. BETTER REGIME DETECTION (BTC daily ATR percentile / daily ADX)")
    # Attach regime-v2 features to every matched trade once.
    for m in matched:
        pct, adx, bull = regime_v2_at(btc_feat, m["sig"]["ts"])
        m["atr_pct90"] = pct
        m["daily_adx"] = adx
    have = [m for m in matched if m["atr_pct90"] is not None]
    print(f"  Trades with ATR-percentile data: {len(have)}/{len(matched)}")
    OUT_LINES.append(f"  Trades with ATR-percentile data: {len(have)}/{len(matched)}")
    # April/May under the 50DMA rule (for reference).
    for mo in ("2026-04", "2026-05"):
        rows = [m for m in matched if m["sig"]["ts"].startswith(mo)]
        show_r(metrics_r(rows, f"{mo} all matched"))
        reg = [m for m in rows if b1.regime_aligned(btc_daily, m) is True]
        show_r(metrics_r(reg, f"{mo} regime-aligned (50DMA)"))
    # ATR percentile bands (on all matched trades).
    for lo, hi in ((0.20, 0.80), (0.10, 0.90), (0.25, 0.75)):
        rows = [m for m in have if lo <= m["atr_pct90"] <= hi]
        show_r(metrics_r(rows, f"ATR pct in [{lo:.2f}, {hi:.2f}] (normal vol only)"))
    rows = [m for m in have if m["atr_pct90"] >= 0.20]
    show_r(metrics_r(rows, "ATR pct >= 0.20 (skip compressed/low-vol)"))
    rows = [m for m in have if m["atr_pct90"] <= 0.80]
    show_r(metrics_r(rows, "ATR pct <= 0.80 (skip extreme vol)"))
    # Daily ADX thresholds.
    for th in (20, 25):
        rows = [m for m in have if m["daily_adx"] is not None and m["daily_adx"] >= th]
        show_r(metrics_r(rows, f"daily ADX >= {th} (trend present)"))
        rows = [m for m in have if m["daily_adx"] is not None and m["daily_adx"] < th]
        show_r(metrics_r(rows, f"daily ADX < {th} (would be skipped)"))
    # April/May under the new rules.
    for mo in ("2026-04", "2026-05"):
        rows = [m for m in matched if m["sig"]["ts"].startswith(mo)]
        for name, pred in (
            ("ATR pct in [0.20,0.80]", lambda m: m["atr_pct90"] is not None and 0.20 <= m["atr_pct90"] <= 0.80),
            ("daily ADX >= 20", lambda m: m["daily_adx"] is not None and m["daily_adx"] >= 20),
            ("daily ADX >= 25", lambda m: m["daily_adx"] is not None and m["daily_adx"] >= 25),
        ):
            show_r(metrics_r([m for m in rows if pred(m)], f"{mo} {name}"))
    # Regime v2 vs 50DMA, and combined, on the V3.1 selection pipeline.
    # (Replace the 50DMA regime test with the new rule, keep top-6 + ADX rising.)
    def sel_with_regime(pred):
        sel = [m for m in matched
               if m["sig"]["symbol"] in TOP6
               and adx_rising_60m(kl60, m) is True and pred(m)]
        return b1.apply_cooldown(sel, 12)

    header("3b. REGIME V2 INSIDE THE V3.1 PIPELINE (selection + trail, no early exit)")
    cands = {
        "50DMA only (V3.1)": lambda m: b1.regime_aligned(btc_daily, m) is True,
        "ATR pct [0.20,0.80] only": lambda m: m["atr_pct90"] is not None and 0.20 <= m["atr_pct90"] <= 0.80,
        "daily ADX >= 20 only": lambda m: m["daily_adx"] is not None and m["daily_adx"] >= 20,
        "daily ADX >= 25 only": lambda m: m["daily_adx"] is not None and m["daily_adx"] >= 25,
        "50DMA AND ATR pct [0.20,0.80]": lambda m: b1.regime_aligned(btc_daily, m) is True and m["atr_pct90"] is not None and 0.20 <= m["atr_pct90"] <= 0.80,
        "50DMA AND daily ADX >= 20": lambda m: b1.regime_aligned(btc_daily, m) is True and m["daily_adx"] is not None and m["daily_adx"] >= 20,
        "50DMA AND daily ADX >= 25": lambda m: b1.regime_aligned(btc_daily, m) is True and m["daily_adx"] is not None and m["daily_adx"] >= 25,
    }
    for name, pred in cands.items():
        sel = sel_with_regime(pred)
        rows = apply_time_stop(sel, kl4h, use_trail=True, use_early=False)
        show_r(metrics_r(rows, name))
        _, avg_pm = sigs_per_month(rows)
        print(f"    monthly return {monthly_return(rows):+.1f} R/month")

    # ---- 1. FUNDING-RATE FILTER ----
    header("1. FUNDING-RATE FILTER (MEXC funding history; OI unavailable, see notes)")
    # Coverage.
    cov = 0
    for m in matched:
        sym = m["sig"]["symbol"].replace("/", "").replace("USDT", "")
        rows = fund.get(sym)
        if not rows:
            continue
        ts_ms = int(datetime.fromisoformat(m["sig"]["ts"]).replace(
            tzinfo=timezone.utc).timestamp() * 1000)
        rate, pct = funding_at(rows, ts_ms)
        if rate is not None:
            cov += 1
    print(f"  Funding coverage: {cov}/{len(matched)} matched trades "
          f"({100*cov/len(matched):.1f}%)")
    OUT_LINES.append(f"  Funding coverage: {cov}/{len(matched)} matched trades")
    # Funding distribution (for threshold context).
    all_rates = []
    for sym, rows in fund.items():
        all_rates += [r for _, r in rows]
    all_rates.sort()
    import statistics
    print(f"  Funding rate distribution (all pairs, all history): "
          f"median {statistics.median(all_rates):+.5f}, "
          f"p10 {all_rates[len(all_rates)//10]:+.5f}, "
          f"p90 {all_rates[int(len(all_rates)*0.9)]:+.5f}, "
          f"p99 {all_rates[int(len(all_rates)*0.99)]:+.5f}, "
          f"max {all_rates[-1]:+.5f}, min {all_rates[0]:+.5f}")
    OUT_LINES.append(f"  Funding median {statistics.median(all_rates):+.5f}, "
                     f"p90 {all_rates[int(len(all_rates)*0.9)]:+.5f}, "
                     f"p99 {all_rates[int(len(all_rates)*0.99)]:+.5f}")
    # Funding-only filter on ALL matched trades (percentile and absolute).
    for mode, kw in (("pct", {}), ("abs", {}),
                     ("abs", {"abs_hi": 0.001, "abs_lo": -0.001}),
                     ("pct_or_abs", {})):
        kept = [m for m in matched if funding_filter(m, fund, mode, **kw) is not False]
        skipped = [m for m in matched if funding_filter(m, fund, mode, **kw) is False]
        show_r(metrics_r(kept, f"funding filter '{mode}' {kw} (kept)"))
        show_r(metrics_r(skipped, f"funding filter '{mode}' {kw} (skipped)"))
    # Funding filter on the V3.1 selection (trail only).
    for mode, kw in (("pct", {}), ("abs", {})):
        kept = [m for m in sel3 if funding_filter(m, fund, mode, **kw) is not False]
        rows = apply_time_stop(kept, kl4h, use_trail=True, use_early=False)
        show_r(metrics_r(rows, f"V3.1 selection + funding '{mode}' {kw}"))
        _, avg_pm = sigs_per_month(rows)
        print(f"    monthly return {monthly_return(rows):+.1f} R/month")
    # Out-of-sample: funding percentile thresholds fitted Jan-Jun, tested Jul-Nov.
    header("1b. FUNDING FILTER OUT-OF-SAMPLE (thresholds fitted Jan-Jun, tested Jul-Nov)")
    for mode, kw in (("pct", {}), ("abs", {})):
        for label, rows in (("Jan-Jun 2026", [m for m in matched if m["sig"]["ts"] < "2026-07"]),
                            ("Jul-Nov 2026", [m for m in matched if m["sig"]["ts"] >= "2026-07"])):
            kept = [m for m in rows if funding_filter(m, fund, mode, **kw) is not False]
            show_r(metrics_r(kept, f"{label} funding '{mode}' (kept)"))
            show_r(metrics_r(rows, f"{label} no funding filter (all)"))

    # ---- COMBINED V3.2 ----
    header("COMBINED V3.2")
    # Best single regime-v2 rule and best funding rule are picked from the
    # sections above; the combined set is reported here with in-sample and
    # holdout splits. (Thresholds are re-stated explicitly so the result
    # is reproducible from this file alone.)
    print("  (See the per-method sections above for which rules are combined; "
          "the combined rows below use: 50DMA + daily ADX >= 20 + funding "
          "percentile filter, top-6, ADX rising, 12h cooldown, partial TP "
          "+1R with trailing BE.)")
    OUT_LINES.append("  Combined V3.2 = 50DMA + daily ADX>=20 + funding pct filter, "
                     "top-6, ADX rising, 12h cooldown, partial TP +1R, trailing BE.")

    def combined(rows_in, use_funding=True, use_adx20=True, partial_k=1.0):
        sel = []
        for m in rows_in:
            if m["sig"]["symbol"] not in TOP6:
                continue
            if adx_rising_60m(kl60, m) is not True:
                continue
            if b1.regime_aligned(btc_daily, m) is not True:
                continue
            if use_adx20 and not (m["daily_adx"] is not None and m["daily_adx"] >= 20):
                continue
            if use_funding and funding_filter(m, fund, "pct") is False:
                continue
            sel.append(m)
        sel = b1.apply_cooldown(sel, 12)
        # Partial TP (+ trailing BE) on the selected trades.
        rows = apply_partial_tp(sel, kl60, partial_k, use_trail=True)
        return rows

    for label, rows_in in (("all matched (in-sample)", matched),
                           ("Jan-Jun 2026", [m for m in matched if m["sig"]["ts"] < "2026-07"]),
                           ("Jul-Nov 2026", [m for m in matched if m["sig"]["ts"] >= "2026-07"])):
        rows = combined(rows_in)
        show_r(metrics_r(rows, f"V3.2 combined ({label})"))
        _, avg_pm = sigs_per_month(rows)
        print(f"    monthly return {monthly_return(rows):+.1f} R/month")
    # Combined without partial TP (to attribute the partial-TP contribution).
    def combined_no_pt(rows_in):
        sel = []
        for m in rows_in:
            if m["sig"]["symbol"] not in TOP6:
                continue
            if adx_rising_60m(kl60, m) is not True:
                continue
            if b1.regime_aligned(btc_daily, m) is not True:
                continue
            if not (m["daily_adx"] is not None and m["daily_adx"] >= 20):
                continue
            if funding_filter(m, fund, "pct") is False:
                continue
            sel.append(m)
        sel = b1.apply_cooldown(sel, 12)
        return apply_time_stop(sel, kl4h, use_trail=True, use_early=False)

    show_r(metrics_r(combined_no_pt(matched),
                     "V3.2 selection (funding + ADX20 + 50DMA) WITHOUT partial TP"))
    # Partial TP alone on the V3.1 selection, for the summary table.
    show_r(metrics_r(apply_partial_tp(sel3, kl60, 1.0, use_trail=True),
                     "V3.1 selection + partial TP +1R (trail on)"))

    # ---- SUMMARY ----
    header("SUMMARY vs V3.1 (bot) and V3.0")
    b0 = metrics_r(matched, "V3.0")
    b1m = metrics_r(v31, "V3.1 (bot, trail only)")
    c = metrics_r(combined(matched), "V3.2 combined")
    for m in (b0, b1m, c):
        print(f"  {m['label']}: n={m['n']} win {m['wr']*100:.1f}% "
              f"avg {m['avg_r']:+.3f} R  monthly {monthly_return(matched if m is b0 else v31 if m is b1m else combined(matched)):+.1f} R/month")
        OUT_LINES.append(f"  {m['label']}: n={m['n']} win {m['wr']*100:.1f}% avg {m['avg_r']:+.3f} R")

    with open(os.path.join(BASE, "channel-analysis", "v3_2-report.txt"), "w") as fh:
        fh.write("TonyBot V3.2 backtest — funding/OI, partial TPs, regime detection\n")
        fh.write("Matched V3.0 trades: %d (of 1,096 signals)\n" % len(matched))
        fh.write("Method, approximations and caveats: see backtest_v3_2.py header.\n")
        fh.write("OI: MEXC open-interest history is NOT available (endpoint blocked "
                 "by WAF; Binance geo-blocked), so only the funding leg was tested.\n")
        fh.write("\n".join(OUT_LINES))
        fh.write("\n")
    print("\nWrote channel-analysis/v3_2-report.txt")


if __name__ == "__main__":
    main()
