"""Equity curves from $1,000 starting capital for TonyBot V3.0, V3.1, V3.2.

Risk model (the bot's OWN, determinable from its signal messages):
  Every V3.0 signal printed "Account Risk: X%", where X = the SL distance
  as % of price (bot.py: account_risk_pct = sl_distance / price * 100,
  capped at 2.0% — signals above that were skipped). The bot sized each
  trade at 10% margin x 10x leverage = 100% notional, so the account loss
  at the stop equals the SL distance as % of the account. Confirmed in
  signals.json: account_risk_pct / sl_dist_pct has median 1.0 (range
  0.963-1.044, rounding), median risk 1.84%, mean 1.70%, range 0.56-2.0%.
  So per trade: account return = R * account_risk_pct / 100, and the
  account compounds trade by trade in signal-ts order.
  (A fixed 1% risk/trade sensitivity is also computed for comparison.)

R per trade comes from the same backtest code that produced the V3.1/V3.2
reports (backtest_improvements / backtest_v3_2), so the R sequences match
the reported averages exactly. V3.0 = all 1,015 matched trades, original R.
V3.1 = selection (50DMA regime + top-6 + ADX rising + 12h cooldown) with
trailing-BE time-stop sim, trail only (the bot as it runs). V3.2 =
recommended version: ATR-percentile [0.20, 0.80] REPLACING the 50DMA,
top-6, ADX rising, 12h cooldown, trailing BE; funding filter and partial
take-profits OFF (both were tested and rejected).

Cutoff: 09:00 WAT, 11 Nov 2026 (08:00 UTC). All 1,015 matched trades
closed before that time (last outcome 2026-11-10T16:41:19Z), so no trade
is excluded by the cutoff. Signals with no matched outcome (81 of 1,096)
are excluded; any still open at the cutoff contribute no realised P&L.

Trades are applied sequentially in signal-ts order. Concurrent positions
are not modelled as reducing available margin (the bot sized each trade
independently); this is the standard sequential equity-curve
approximation and matches how the backtests treat the trade list.

Usage: /tmp/tonybot-test-venv/bin/python equity_1000usd.py
"""
import json
import os
from datetime import datetime, timezone

import backtest_improvements as b1
import backtest_v3_2 as b2

BASE = os.path.dirname(os.path.abspath(__file__))
START = 1000.0
CUTOFF_UTC = "2026-11-11T08:00:00"  # 09:00 WAT


def build_versions():
    sigs, matched = b1.load_matched()
    kl4h = b1.load_klines_4h()
    kl60 = b1.load_klines_60m()
    btc_daily = b1.load_btc_daily()
    btc_feat = b2.btc_daily_features()
    for m in matched:
        pct, adx, bull = b2.regime_v2_at(btc_feat, m["sig"]["ts"])
        m["atr_pct90"] = pct
        m["daily_adx"] = adx

    # V3.0: all matched trades, original R.
    v30 = list(matched)

    # V3.1 as the bot runs: selection + trailing BE, no early exit.
    sel3 = b2.v3_1_selection(matched, kl60, btc_daily)
    v31 = b2.apply_time_stop(sel3, kl4h, use_trail=True, use_early=False)

    # V3.2 recommended: ATR [0.20, 0.80] REPLACING the 50DMA.
    def atr_only(m):
        return (m["atr_pct90"] is not None
                and 0.20 <= m["atr_pct90"] <= 0.80)

    sel32 = [m for m in matched
             if m["sig"]["symbol"] in b1.TOP6
             and b2.adx_rising_60m(kl60, m) is True
             and atr_only(m)]
    sel32 = b1.apply_cooldown(sel32, 12)
    v32 = b2.apply_time_stop(sel32, kl4h, use_trail=True, use_early=False)
    return sigs, matched, v30, v31, v32


def equity_curve(rows, risk_mode="bot"):
    """Compound $1,000 through the trades in signal-ts order.
    risk_mode 'bot': per-trade account_risk_pct from the signal (the bot's
    own risk). risk_mode 'fixed1': flat 1% risk per trade (sensitivity).
    Returns (equity list of (ts, equity_after), final, total_r, stats)."""
    eq = START
    curve = []
    peak = START
    max_dd = 0.0
    max_dd_pct = 0.0
    total_r = 0.0
    wins = losses = bes = 0
    for m in rows:
        r = m["r"]
        total_r += r
        if risk_mode == "bot":
            risk_pct = m["sig"].get("account_risk_pct") or m["sig"]["sl_dist_pct"]
        else:
            risk_pct = 1.0
        ret = r * risk_pct / 100.0
        eq *= (1.0 + ret)
        if r > 1e-9:
            wins += 1
        elif r < -1e-9:
            losses += 1
        else:
            bes += 1
        if eq > peak:
            peak = eq
        dd = peak - eq
        dd_pct = dd / peak * 100.0 if peak else 0.0
        if dd > max_dd:
            max_dd = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
        curve.append((m["sig"]["ts"], m["sig"]["symbol"], m["sig"]["type"],
                      r, risk_pct, eq))
    stats = {"n": len(rows), "wins": wins, "losses": losses, "be": bes,
             "total_r": total_r,
             "avg_r": total_r / len(rows) if rows else 0.0,
             "final": eq, "pnl": eq - START,
             "max_dd_usd": max_dd, "max_dd_pct": max_dd_pct}
    return curve, stats


def monthly_snapshots(curve):
    """Equity at the end of each YYYY-MM month present in the curve."""
    snaps = {}
    for ts, sym, typ, r, risk, eq in curve:
        snaps[ts[:7]] = eq
    return snaps


def main():
    sigs, matched, v30, v31, v32 = build_versions()
    # Cutoff check: all matched outcomes close before 09:00 WAT 11 Nov 2026.
    late = [m for m in matched if m["out"]["ts"] >= CUTOFF_UTC]
    unmatched = len(sigs) - len(matched)
    print(f"Matched trades: {len(matched)} (of {len(sigs)} signals)")
    print(f"Outcomes closing at/after cutoff {CUTOFF_UTC}Z: {len(late)}")
    print(f"Signals with no matched outcome: {unmatched}")
    print(f"Last matched outcome: {max(m['out']['ts'] for m in matched)}")
    print(f"Last signal: {max(s['ts'] for s in sigs)}")

    versions = [("V3.0 (original, all matched)", v30),
                ("V3.1 (bot: 50DMA + top-6 + ADX rising + 12h cooldown + trailing BE)", v31),
                ("V3.2 (ATR [0.20,0.80] replacing 50DMA; funding + partial TP OFF)", v32)]

    lines = []
    lines.append("TonyBot equity curves from $1,000 starting capital")
    lines.append("Cutoff: 09:00 WAT, 11 Nov 2026 (08:00 UTC) — when the bot went quiet.")
    lines.append("All 1,015 matched trades closed before the cutoff; no trade excluded.")
    lines.append("")
    lines.append("RISK MODEL (the bot's own, from its signal messages):")
    lines.append("  Each signal printed 'Account Risk: X%', where X = SL distance as %")
    lines.append("  of price (bot.py: account_risk_pct = sl_distance/price*100, cap 2.0%).")
    lines.append("  The bot sized each trade at 10% margin x 10x leverage = 100% notional,")
    lines.append("  so the account loss at the stop = SL distance % of the account.")
    lines.append("  Confirmed in signals.json: account_risk_pct/sl_dist_pct median 1.0,")
    lines.append("  median risk 1.84%, mean 1.70%, range 0.56-2.0% (n=1,096).")
    lines.append("  Per trade: account return = R x account_risk_pct / 100, compounded")
    lines.append("  in signal-ts order. A fixed-1%-risk sensitivity is shown for comparison.")
    lines.append("  R is the backtest R (pnl_pct / (sl_dist_pct x 10)), trailing-BE")
    lines.append("  simulated for V3.1/V3.2 as in the V3.1/V3.2 reports.")
    lines.append("  Trades applied sequentially in signal order; concurrent positions")
    lines.append("  are not modelled as reducing available margin.")
    lines.append("")

    results = {}
    for label, rows in versions:
        curve, stats = equity_curve(rows, risk_mode="bot")
        curve1, stats1 = equity_curve(rows, risk_mode="fixed1")
        results[label] = (curve, stats, stats1)
        # Sanity check against the reported averages.
        print(f"\n{label}")
        print(f"  n={stats['n']}  win {stats['wins']} loss {stats['losses']} BE {stats['be']}")
        print(f"  total R {stats['total_r']:+.2f}  avg R {stats['avg_r']:+.3f}")
        print(f"  BOT RISK  : final ${stats['final']:,.2f}  P&L ${stats['pnl']:+,.2f}  "
              f"max DD ${stats['max_dd_usd']:,.2f} ({stats['max_dd_pct']:.1f}%)")
        print(f"  FIXED 1%  : final ${stats1['final']:,.2f}  P&L ${stats1['pnl']:+,.2f}  "
              f"max DD ${stats1['max_dd_usd']:,.2f} ({stats1['max_dd_pct']:.1f}%)")
        lines.append(f"========== {label} ==========")
        lines.append(f"  Trades: n={stats['n']}  wins {stats['wins']}  losses {stats['losses']}  "
                     f"breakevens {stats['be']}")
        lines.append(f"  Total R: {stats['total_r']:+.2f}  Avg R/trade: {stats['avg_r']:+.3f}")
        lines.append(f"  BOT RISK MODEL (per-trade account_risk_pct, median 1.84%):")
        lines.append(f"    Final account: ${stats['final']:,.2f}  P&L: ${stats['pnl']:+,.2f}  "
                     f"({stats['pnl']/START*100:+.1f}%)")
        lines.append(f"    Max drawdown: ${stats['max_dd_usd']:,.2f} ({stats['max_dd_pct']:.1f}%)")
        lines.append(f"  FIXED 1% RISK SENSITIVITY (1R = 1% of account):")
        lines.append(f"    Final account: ${stats1['final']:,.2f}  P&L: ${stats1['pnl']:+,.2f}  "
                     f"({stats1['pnl']/START*100:+.1f}%)")
        lines.append(f"    Max drawdown: ${stats1['max_dd_usd']:,.2f} ({stats1['max_dd_pct']:.1f}%)")
        snaps = monthly_snapshots(curve)
        lines.append("  Month-end equity (bot risk model):")
        for mo in sorted(snaps):
            lines.append(f"    {mo}: ${snaps[mo]:,.2f}")
        lines.append("")

    # Full per-trade equity curves.
    for label, (curve, stats, stats1) in results.items():
        lines.append(f"========== TRADE-BY-TRADE EQUITY — {label} ==========")
        lines.append("signal_ts | symbol | type | R | risk_pct% | equity_after_usd")
        for ts, sym, typ, r, risk, eq in curve:
            lines.append(f"{ts} | {sym} | {typ} | {r:+.3f} | {risk:.2f} | {eq:,.2f}")
        lines.append("")

    out_path = os.path.join(BASE, "channel-analysis", "equity-1000usd.txt")
    with open(out_path, "w") as fh:
        fh.write("\n".join(lines))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
