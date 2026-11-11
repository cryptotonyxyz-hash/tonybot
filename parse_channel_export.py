"""Parse a Telegram Desktop JSON export of Tony's signal channel and
extract every signal + outcome, so the rebuild's unknown formulas can be
reverse-engineered from real data instead of guessed.

Usage:
    python parse_channel_export.py <export.json> [--out dir]

Telegram Desktop export: open the channel in Telegram Desktop -> three
dots -> Export chat history -> JSON. The file has:
    {"name": ..., "messages": [{"id", "date", "date_unixtime", "from",
     "text": str | [ {type, text} ... ]}, ...]}

What it extracts:
  * Signal alerts: symbol, LONG/SHORT, entry, target, stop, ADX, RSI,
    ATR%, score, leverage, account risk, R:R, invalid-above, timestamp.
  * Outcomes: TP HIT / SL HIT / TIME-STOP EXPIRED with entry, exit, P&L.
  * 4H UPDATE / 24H PERFORMANCE / WEEKLY REPORT totals (incl. career W-L).
  * Per-signal implied SL multiplier (SL distance % / ATR %) and realised
    R:R, so the exact TP/SL formula can be verified.

Outputs (into --out, default ./channel-analysis/):
  * signals.json        — every parsed signal alert
  * outcomes.json       — every parsed outcome
  * summary.json        — aggregates + formula checks
  * stats_seed.json     — wins/losses/history to seed stats.json
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

# ---------------------------------------------------------------- patterns
def flat_text(msg):
    """Telegram export 'text' is a string or a list of entities."""
    t = msg.get("text", "")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p)
                       for p in t)
    return str(t)


NUM = r"[-+]?\d+(?:\.\d+)?"

RE_SIGNAL = re.compile(
    r"(LONG|SHORT)\s+SIGNAL:\s*([A-Z]+/USDT)", re.IGNORECASE)
RE_ENTRY = re.compile(r"Entry:\s*(" + NUM + r")", re.IGNORECASE)
RE_TARGET = re.compile(r"Target:\s*(" + NUM + r")", re.IGNORECASE)
RE_STOP = re.compile(r"Stop Loss:\s*(" + NUM + r")", re.IGNORECASE)
RE_INVALID = re.compile(r"Invalid Above:\s*(" + NUM + r")", re.IGNORECASE)
RE_ADX = re.compile(r"ADX:\s*(" + NUM + r")", re.IGNORECASE)
RE_RSI = re.compile(r"RSI:\s*(" + NUM + r")", re.IGNORECASE)
RE_ATR = re.compile(r"ATR:\s*(" + NUM + r")\s*%", re.IGNORECASE)
RE_SCORE = re.compile(r"Score:\s*(\d+)\s*/\s*10", re.IGNORECASE)
RE_HIGH = re.compile(r"⚡\s*(HIGH|MEDIUM|LOW)", re.IGNORECASE)
# V3.0 confidence label, e.g. "⭐⭐⭐ PREMIUM" on the line after the header.
RE_PREMIUM = re.compile(r"⭐+\s*([A-Z]+)", re.IGNORECASE)
RE_LEV = re.compile(r"Leverage:\s*(\d+)\s*x", re.IGNORECASE)
RE_RISK = re.compile(r"Account Risk:\s*(" + NUM + r")\s*%", re.IGNORECASE)
RE_RR = re.compile(r"Risk/Reward:\s*1\s*:\s*(" + NUM + r")", re.IGNORECASE)

# V3.0 outcomes: "TARGET HIT" (TP win), "STOP HIT" (SL loss),
# "TIME-STOP EXPIRED" (win/loss from the Result line).
# Pre-V3.0 (early 2026) outcomes: short "WIN: X" / "LOSS: X" messages.
RE_OUTCOME = re.compile(
    r"(TARGET HIT|STOP HIT|TIME-STOP EXPIRED|TIME STOP EXPIRED|"
    r"WIN:\s*[A-Z]+/USDT|LOSS:\s*[A-Z]+/USDT)", re.IGNORECASE)
RE_EXIT = re.compile(r"Exit:\s*(" + NUM + r")", re.IGNORECASE)
RE_PNL = re.compile(r"(?:Final\s+)?P&L:\s*(" + NUM + r")\s*%", re.IGNORECASE)
RE_LOSS = re.compile(r"Loss:\s*-?\s*(" + NUM + r")\s*%", re.IGNORECASE)
RE_RESULT = re.compile(r"Result:\s*.*?((?:PROFIT|WIN|LOSS))", re.IGNORECASE)

RE_CAREER = re.compile(
    r"Total Career:\s*(\d+)\s*W\s*-\s*(\d+)\s*L", re.IGNORECASE)
RE_PERF = re.compile(
    r"Total Signals:\s*(\d+)\s*\n.*?Wins:\s*(\d+)\s*\n.*?Losses:\s*(\d+)",
    re.IGNORECASE | re.DOTALL)


def parse_signal(text, ts):
    m = RE_SIGNAL.search(text)
    if not m:
        return None
    def f(pat):
        mm = pat.search(text)
        return float(mm.group(1)) if mm else None
    def s(pat):
        mm = pat.search(text)
        return mm.group(1) if mm else None
    sig = {
        "ts": ts,
        "type": m.group(1).upper(),
        "symbol": m.group(2).upper(),
        "entry": f(RE_ENTRY),
        "target": f(RE_TARGET),
        "stop": f(RE_STOP),
        "invalid_above": f(RE_INVALID),
        "adx": f(RE_ADX),
        "rsi": f(RE_RSI),
        "atr_pct": f(RE_ATR),
        "score": int(s(RE_SCORE)) if s(RE_SCORE) else None,
        "confidence": (RE_HIGH.search(text).group(1).upper()
                       if RE_HIGH.search(text) else None),
        "label": (RE_PREMIUM.search(text).group(1).upper()
                  if RE_PREMIUM.search(text) else None),
        "leverage": int(s(RE_LEV)) if s(RE_LEV) else None,
        "account_risk_pct": f(RE_RISK),
        "risk_reward": f(RE_RR),
    }
    # Derived: SL distance % (= account risk) and realised R:R.
    # The implied SL multiplier needs ATR%, which the alerts do not carry,
    # so it is computed separately (see fetch_atr_multipliers.py).
    if sig["entry"] and sig["stop"]:
        sl_dist_pct = abs(sig["entry"] - sig["stop"]) / sig["entry"] * 100
        sig["sl_dist_pct"] = round(sl_dist_pct, 4)
    if sig["entry"] and sig["target"] and sig["stop"]:
        sl_d = abs(sig["entry"] - sig["stop"])
        tp_d = abs(sig["target"] - sig["entry"])
        if sl_d:
            sig["realised_rr"] = round(tp_d / sl_d, 3)
    return sig


def parse_outcome(text, ts):
    m = RE_OUTCOME.search(text)
    if not m:
        return None
    kind = m.group(1).upper()
    # Normalise the kind to TARGET_HIT / STOP_HIT / TIME_STOP / WIN / LOSS.
    if "TARGET HIT" in kind:
        kind = "TARGET_HIT"
        win = True
    elif "STOP HIT" in kind:
        kind = "STOP_HIT"
        win = False
    elif "TIME-STOP" in kind or "TIME STOP" in kind:
        kind = "TIME_STOP"
        res = RE_RESULT.search(text)
        # Result line reads "🟢 PROFIT" for a win, "🔴 LOSS" for a loss.
        win = (res.group(1).upper() in ("PROFIT", "WIN")) if res else None
    elif kind.startswith("WIN"):
        kind = "WIN"
        win = True
    elif kind.startswith("LOSS"):
        kind = "LOSS"
        win = False
    else:
        win = None
    def f(pat):
        mm = pat.search(text)
        return float(mm.group(1)) if mm else None
    pnl = f(RE_PNL)
    if pnl is None:
        loss = f(RE_LOSS)
        if loss is not None:
            pnl = -abs(loss)
    sym = RE_SIGNAL.search(text)
    if not sym:
        sym = re.search(r"(?:TARGET HIT|STOP HIT|WIN|LOSS):\s*([A-Z]+/USDT)",
                        text, re.IGNORECASE)
    return {
        "ts": ts,
        "kind": kind,
        "symbol": sym.group(1).upper() if sym else None,
        "entry": f(RE_ENTRY),
        "exit": f(RE_EXIT),
        "pnl_pct": pnl,
        "win": win,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_json")
    ap.add_argument("--out", default="channel-analysis")
    args = ap.parse_args()

    with open(args.export_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    messages = data.get("messages", [])
    print(f"Loaded {len(messages)} messages from {args.export_json}")

    signals, outcomes, careers, perfs = [], [], [], []
    unmatched = 0
    for msg in messages:
        text = flat_text(msg)
        if not text.strip():
            continue
        ts = msg.get("date") or msg.get("date_unixtime")
        # Only the bot's messages carry these markers; skip chatter.
        matched = False
        sig = parse_signal(text, ts)
        if sig:
            signals.append(sig)
            matched = True
        else:
            out = parse_outcome(text, ts)
            if out:
                outcomes.append(out)
                matched = True
        cm = RE_CAREER.search(text)
        if cm:
            careers.append({"ts": ts, "wins": int(cm.group(1)),
                            "losses": int(cm.group(2))})
            matched = True
        pm = RE_PERF.search(text)
        if pm:
            perfs.append({"ts": ts, "total": int(pm.group(1)),
                          "wins": int(pm.group(2)),
                          "losses": int(pm.group(3))})
            matched = True
        if not matched and ("SIGNAL" in text or "HIT" in text
                            or "EXPIRED" in text or "PERFORMANCE" in text
                            or "UPDATE" in text):
            unmatched += 1

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "signals.json"), "w") as fh:
        json.dump(signals, fh, indent=2)
    with open(os.path.join(args.out, "outcomes.json"), "w") as fh:
        json.dump(outcomes, fh, indent=2)

    # ---- aggregates / formula checks ----
    mults = [s["implied_sl_multiplier"] for s in signals
             if s.get("implied_sl_multiplier") is not None]
    rrs = [s["realised_rr"] for s in signals if s.get("realised_rr") is not None]
    scores = Counter(s["score"] for s in signals if s.get("score") is not None)
    labels = Counter(s.get("label") for s in signals if s.get("label"))
    pairs = Counter(s["symbol"] for s in signals)
    types = Counter(s["type"] for s in signals)
    kinds = Counter(o["kind"] for o in outcomes)
    wins = sum(1 for o in outcomes if o.get("win") is True)
    losses = sum(1 for o in outcomes if o.get("win") is False)
    # SL distance % (= account risk) distribution.
    sl_dists = [s["sl_dist_pct"] for s in signals if s.get("sl_dist_pct")]
    # "Invalid Above" factor: for SHORTs, (entry - invalid_above) / SL distance.
    inv_factors = []
    for s in signals:
        if (s.get("type") == "SHORT" and s.get("invalid_above") is not None
                and s.get("entry") and s.get("stop")):
            sl_d = abs(s["entry"] - s["stop"])
            if sl_d:
                inv_factors.append(
                    round((s["entry"] - s["invalid_above"]) / sl_d, 3))

    def dist(vals):
        if not vals:
            return {}
        vals = sorted(vals)
        return {"n": len(vals), "min": vals[0], "max": vals[-1],
                "median": vals[len(vals) // 2],
                "mean": round(sum(vals) / len(vals), 3),
                "mode": Counter(vals).most_common(3)}

    summary = {
        "messages_total": len(messages),
        "signals_parsed": len(signals),
        "outcomes_parsed": len(outcomes),
        "outcomes_wins": wins,
        "outcomes_losses": losses,
        "outcomes_win_rate_pct": round(
            wins / max(wins + losses, 1) * 100, 1),
        "pairs_seen": dict(pairs),
        "types": dict(types),
        "outcome_kinds": dict(kinds),
        "score_distribution": {str(k): v for k, v in sorted(scores.items())},
        "label_distribution": dict(labels),
        "sl_dist_pct": dist(sl_dists),
        "invalid_above_factor": dist(inv_factors),
        "implied_sl_multiplier": dist(mults),
        "realised_rr": dist(rrs),
        "latest_career": careers[-1] if careers else None,
        "career_samples": len(careers),
        "performance_reports": len(perfs),
        "unmatched_bot_like_messages": unmatched,
    }
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # ---- stats seed for the rebuild ----
    hist = [{"ts": o["ts"], "win": bool(o["win"])} for o in outcomes
            if o.get("win") is not None and o.get("ts")]
    seed = {
        "wins": careers[-1]["wins"] if careers else wins,
        "losses": careers[-1]["losses"] if careers else losses,
        "history": hist,
        "last_report_4h": None,
        "last_report_week": None,
    }
    with open(os.path.join(args.out, "stats_seed.json"), "w") as fh:
        json.dump(seed, fh, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nWrote: signals.json, outcomes.json, summary.json, stats_seed.json"
          f" -> {args.out}/")


if __name__ == "__main__":
    main()
