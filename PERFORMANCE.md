# TonyBot V3.0 — Performance Analysis & Improvement Plan

Source: full export of "Tony's signal channel" (1,096 V3.0 signals,
1,041 outcomes, Jan 9 – Nov 11, 2026). 1,015 outcomes matched to signals
(97.5%). Analysis script: `analyse_performance.py`, full output in
`channel-analysis/performance-report.txt`.

## Current version (adopted Nov 11, 2026): V3.2 — ATR regime

**`bot_v3_2.py` is the adopted current version.** It is V3.1 with the
50DMA regime filter REPLACED by the BTC daily ATR(14) percentile band
[0.20, 0.80] (only trade when volatility is in the normal range). Kept
from V3.1: top-6 pairs, ADX rising (60m), 12h post-loss cooldown,
trailing stop to breakeven at +0.8R, rebuilt PREMIUM label. SL 1.25x
ATR(4h) and R:R 1:1.8 unchanged. Backtest: **138 trades, 52.9% win,
+0.560 R/trade, ~+7.0 R/month** (vs V3.1: 183 trades, 45.9% win,
+0.411 R; vs V3.0: 42.2% win, +0.018 R). **Tested and REJECTED, both
OFF by default in `bot_v3_2.py`:** the funding-rate filter (premise
backwards — extreme-funding trades are the best, not the worst; OI
history unobtainable) and partial take-profits (lifts win rate but
lowers avg R in every test, and the win-rate lift vanishes
out-of-sample). See the V3.2 section below for the full evidence.
Equity from $1,000 (bot's own per-trade risk, compounding):
`channel-analysis/equity-1000usd.txt` — V3.0 $1,063.49 (+$63.49),
V3.1 $3,387.60 (+$2,387.60), V3.2 $3,769.99 (+$2,769.99), as of
09:00 WAT, 11 Nov 2026. Do NOT deploy with real money on a backtest
alone — forward-test live first. Nothing pushed to GitHub without
Anthony's explicit approval.

## The headline

The bot is **breakeven, not broken**. Average P&L is **+0.018 R per trade**
— it treads water. The win rate is 42.4% (435W-591L), which sounds bad,
but with a 1:1.8 R:R the breakeven win rate is only 41.3%, so it just
about covers its losses. The problem is it makes no money, and it used
to make money: **Jan–Feb it won 68–74% of trades, then collapsed to
~24–52% from March onward.**

## What worked

1. **The 24h time-stop is the best part of the bot.** 400 trades (38% of
   all outcomes) ended on the time-stop. 54.5% of them were profitable
   (avg +8.7%), 45.5% lost (avg -6.7%). Net: **+1.72% per time-stop**.
   It cuts drifting trades before they hit the full stop (-16.7% avg),
   and banks small profits. Keep it. It is the main reason the bot is
   breakeven instead of losing.
2. **SHORTs in a real downtrend.** Jan SHORTs won 83.3%, Feb SHORTs
   78.9%. When the market is clearly falling, the bot's SHORTs ride it.
   The direction filter works when the trend is real.
3. **Strong trends (ADX 50+).** 52.3% win rate (n=44) — the only ADX
   bucket that clearly beats the average. Genuinely strong trends
   follow through.
4. **The R:R (1:1.8) is sound.** Avg winning trade +1.15 R, avg losing
   trade -0.80 R (both shrunk by the time-stop). The math is not the
   problem.
5. **The best pairs trend cleanly.** LINK 49.3%, SOL 48.9%, LTC 48.4%,
   ETH 44.9%, XRP 43.5%, BTC 42.9% — all above the 42% average.

## What didn't work

1. **Over-trading in choppy markets.** Signal count exploded from
   ~35/month (Jan–Feb) to 100–194/month (Mar–Oct) while the win rate
   collapsed. The ADX>=25 filter is too loose: it fires constantly on
   weak, short-lived trends that reverse. Jan–Feb the bot was selective
   and good; after March it fired 3–5x as often at a much lower win rate.
2. **No market-regime filter.** The bot trades LONG and SHORT regardless
   of the macro trend. April LONGs won **3.4% (1 of 29)** — it kept
   buying into a falling market. September SHORTs won 22.0% while LONGs
   won 61.9%; October flipped (LONGs 26.3%, SHORTs 55.2%). The market
   regime flips often, and the bot gets whipsawed because it has no
   view on which direction the market is actually going.
3. **The PREMIUM/HIGH label is meaningless.** PREMIUM won 41.4%,
   HIGH won 43.0%. The label does not predict wins. The score behind
   it adds nothing.
4. **Weak pairs drag the average.** NEAR 27.3% (n=22), UNI 33.3%
   (n=15), ADA 36.4%, DOGE 36.6%. These four are all below average.
5. **ADX doesn't filter well.** Win rate is flat (39–43%) across
   ADX 25–50. Only ADX 50+ stands out (52.3%). Raising the threshold
   to 30 or 35 would barely help; the filter needs rethinking, not
   just a higher number.
6. **The win rate is too low to profit.** At 42% and 1:1.8 it breaks
   even. It needs ~45%+ (or a better R:R, or fewer but better trades)
   to actually make money.

## The regime story (why it went bad)

- **Jan–Feb: trending market, bot selective.** BTC near $89k, then
  falling. ~35 signals/month, 68–74% win rate, SHORTs dominant.
- **Mar onward: choppy/ranging market, bot over-trading.** BTC stuck
  in the $60k–$80k range. 100–194 signals/month, win rate 24–52%,
  settling around 40–47%. The trend-following logic fires on noise.
- The user's read is directionally right (the market changed after
  BTC left the $90k area), but the mechanism is **trend quality, not
  price level**: the market went from trending to choppy, and a
  trend-following bot without a regime filter loses in chop.

## The plan (in priority order)

### 1. Add a market-regime filter (highest impact)
Only take signals in the direction of the macro trend. When BTC is in
a clear downtrend (e.g. below its 50-day moving average, or the 4H
trend has been bearish for days), take SHORTs only. When BTC is in a
clear uptrend, take LONGs only. This alone would have prevented the
April LONG disaster (3.4%) and the September SHORT disaster (22%).
Implementation: check BTC vs its 50-day MA (or a 4H EMA200) before
firing any signal; skip the signal if it goes against the macro trend.

### 2. Tighten the entry filter (stop the over-trading)
- Require ADX to be **rising** (not just above 25), so the bot only
  fires when momentum is building, not fading.
- Add a minimum trend-strength check on the 4H (e.g. price clearly
  beyond EMA50, not just barely above/below it).
- Consider a short cool-down after a loss on the same pair, so a
  choppy pair can't fire five losing signals in a row.
Goal: get back toward ~50–70 signals/month, not 100–190.

### 3. Drop or deprioritise the worst pairs
Remove NEAR (27.3%) and UNI (33.3%). Consider dropping ADA and DOGE
too, or keep them only when the regime filter agrees. Focus the bot
on LINK, SOL, LTC, ETH, XRP, BTC — the six pairs at 43–49%.

### 4. Rebuild or drop the PREMIUM/HIGH label
The current score (ADX + RSI) doesn't predict wins. Rebuild it from
what actually works (ADX 50+ is the only strong signal), or drop the
label and send every signal at the same confidence. Do not keep a
label that misleads.

### 5. Improve the time-stop (already good, make it better)
- Add a **trailing stop / breakeven move**: once a trade is in
  profit by ~0.8 R, move the stop to breakeven. This locks in the
  time-stop winners and stops reversals eating them.
- Consider an **early exit for red trades**: if a trade is still in
  the red after 12h, exit early instead of waiting the full 24h.
  This cuts the losing time-stops (-6.7% avg) further.

### 6. Backtest before deploying
Run the improved rules against the 1,096 recorded signals and check
the win rate and expected value actually improve. Do not change the
live bot on a hunch — verify with the data first. The analysis
scripts in this folder can be extended into a backtester.

## Expected outcome (if the plan works)
- Win rate 42% → ~46–50% (regime filter + fewer, better signals).
- At 47% win rate and the same sizes, expected value goes from
  +0.02 R/trade to roughly +0.15 R/trade — the bot starts making
  money instead of treading water.
- Fewer signals (less noise, less Telegram spam), higher quality.

---

## V3.1 — Backtest results (built Nov 11, 2026)

The plan above was implemented in `bot_v3_1.py` (V3.0 `bot.py` untouched)
and backtested against the 1,015 matched trades. Backtest script:
`backtest_improvements.py`; full output:
`channel-analysis/improvements-report.txt`. Data: MEXC 4H klines for all
15 pairs, 60m klines for all 14 listed pairs (TON delisted), BTC daily
klines from Nov 2025 (for the 50DMA). R = pnl_pct / (sl_dist_pct x 10).

### Headline

| Version | Trades | Win rate | Avg R/trade | Signals/month |
|---|---|---|---|---|
| V3.0 baseline | 1,015 | 42.3% | +0.018 R | 92 |
| V3.1 full (all filters) | 183 | 51.4% | +0.374 R | 17 |
| V3.1 mild (regime + ADX rising) | 348 | 51.4% | +0.293 R | 32 |
| ADX rising only | 590 | 49.3% | +0.202 R | 54 |

Monthly expected return (avg R x trades/month): baseline +1.7 R/month,
ADX rising only +10.8 R/month, regime + ADX rising +9.3 R/month, full
V3.1 +6.4 R/month. The per-trade edge rises as filters stack, but the
trade count falls faster, so the highest monthly return comes from the
single strongest filter, not from stacking all of them.

### Each improvement, with numbers

1. **Regime filter (BTC vs 50DMA): HELPED.** Aligned trades: 46.1% win,
   +0.124 R (n=573). Against-trades: 37.3% win, -0.120 R (n=442) — the
   filter removes genuinely bad trades. SHORTs aligned: 50.5% win,
   +0.251 R. LONGs aligned: only 41.8% win, +0.002 R — the filter helps
   SHORTs far more than LONGs. **Caveat: it does NOT fix April.** All 29
   April LONGs were regime-aligned (BTC closed above its 50DMA 26/30
   days in April) and still won 3.4%. April was chop, not a downtrend,
   and a 50DMA cannot catch chop.
2. **ADX rising (60m ADX now > prev 60m candle): HELPED MOST.**
   49.3% win, +0.202 R (n=590, 54/month). Flat/falling ADX trades:
   32.1% win, -0.252 R (n=411) — the filter cuts the worst trades.
   ADX >= 30 instead of 25: NO HELP (41.6% vs 42.8% for ADX 25-30),
   not adopted.
3. **Drop NEAR + UNI / top-6 only: HELPED.** Top-6: 45.8% win, +0.098 R
   (n=594, 54/month). NEAR+UNI alone: 29.7% win, -0.255 R (n=37).
   Dropping the two worst pairs is clearly right.
4. **PREMIUM label rebuilt: SEPARATES, but small n.** PREMIUM = ADX >= 50
   AND regime-aligned: 22 trades, 59.1% win, +0.553 R. The rest: 41.9%
   win, +0.006 R. ADX >= 50 alone: 44 trades, 52.3%, +0.356 R. The new
   label means something now, but with n=22 it is a label only, not a
   trade filter. (The old label was meaningless: PREMIUM 41.4% vs HIGH
   43.0%.)
5. **Trailing stop to breakeven at +0.8R: SMALL HELP.** +0.018 R ->
   +0.040 R unfiltered; +0.367 R -> +0.374 R on the filtered set. Kept:
   principled risk management, low cost. **12h early exit for red
   trades: NO HELP** (+0.000 R alone, and it cancels the trailing-stop
   gain when combined). Not adopted.
6. **Post-loss cooldown: SMALL HELP at 12h, HURTS at 24h.** 12h: 44.4%
   win, +0.074 R (n=628, 57/month). 24h: 39.5% win, -0.004 R — sitting
   out a full day after a loss skips good trades too. 12h kept, 24h
   dropped. (An earlier run of this test had a look-ahead bug — it
   skipped signals that arrived while the losing trade was still open,
   before the loss was known — and showed a bogus 58.9% win rate. The
   bug was caught and fixed: the blackout now starts at the loss's
   close time. The corrected 12h figure is +0.074 R, not +0.445 R.)

### What was NOT adopted
- ADX >= 30 (no separation). 24h post-loss cooldown (hurts). 12h early
  exit for red trades (no help). SL rule (1.25x ATR 4h) and R:R 1:1.8
  unchanged — the backtest gave no reason to move them.

### Two discoveries while building this
- **The bot's ADX is a 1-hour ADX.** The recorded signal ADX values
  match ADX(14) on 60m candles (median abs diff 0.96 across 1,033
  signals; 850 within 2), but NOT 4H ADX(14) (median abs diff ~9-10)
  or 15m (median abs diff ~10-11). The V3.0 rebuild computed ADX from
  4H candles — a fidelity bug, corrected in V3.1. The trend filter
  still uses 4H + 15M EMA50s.
- **TONUSDT is delisted on MEXC.** Its klines endpoint returns
  "Invalid symbol". TON (22 signals, 2.0%) was excluded from the
  kline-dependent tests only (ADX rising, time-stop); it is included
  in the regime/pair/cooldown/label tests. Binance and OKX fallbacks
  were blocked/unavailable from the sandbox.

### Recommendation
- **Default V3.1 (implemented in `bot_v3_1.py`):** regime filter +
  ADX rising (60m) + top-6 pairs + trailing stop to breakeven at +0.8R
  + 12h post-loss cooldown + rebuilt PREMIUM label. Backtest: 51.4%
  win, +0.374 R/trade, ~17 signals/month.
- **If ~50 signals/month matters more than max per-trade edge:**
  ADX rising alone (49.3% win, +0.202 R, 54/month) or regime + ADX
  rising (51.4% win, +0.293 R, 32/month). These are the most robust
  choices — single rules, least overfit.
- **Honesty note:** this is an in-sample backtest — the filters were
  chosen because they looked good on this same data, so the combined
  +0.374 R is likely optimistic. The single-filter results (ADX rising
  +0.202 R, regime +0.124 R, top-6 +0.098 R) are the most trustworthy.
  April/May remain weak even with all filters (April 0.0% win, n=8 in
  the full V3.1 set), so the bot still has bad months. Do not deploy
  with real money on this backtest alone; forward-test the V3.1 rules
  on live signals first, and do not push to GitHub without Anthony's
  explicit approval.
- **Files:** `bot_v3_1.py` (all V3.1 flags can be turned off individually
  to reproduce V3.0), `test_v3_1.py` (21 smoke tests, all passing),
  `backtest_improvements.py`, `fetch_klines.py`,
  `channel-analysis/klines/` (4H + 60m + BTC daily),
  `channel-analysis/improvements-report.txt`.

---

## V3.2 — Funding/OI, partial TPs, regime detection (Nov 11, 2026)

Three further methods tested on top of V3.1 (backtest script
`backtest_v3_2.py`; full numbers in `channel-analysis/v3_2-report.txt`).
SL (1.25x ATR 4h) and R:R 1:1.8 unchanged throughout. R = pnl_pct /
(sl_dist_pct x 10). Win = adjusted R > 0; R == 0 counts as breakeven.
All numbers below are post-simulation (after the trailing stop / partial
TP), unless labelled "selection-only".

### Win-rate definition correction (applies to V3.1 too)
The V3.1 report's 51.4% win rate is the PRE-simulation win rate (it
counted wins from the original outcome). After the trailing stop to
breakeven converts some outcomes to 0R, the V3.1 strategy's true win
rate is **45.9% with 30 breakevens (16.4%)**. Average R is unaffected
and is the correct expectancy measure. The same applies to every
trailing-BE / partial-TP row in V3.2: win rate is post-simulation,
breakevens are shown. V3.1 as the bot actually runs (trailing BE only,
no 12h early exit): **183 trades, 45.9% win, +0.411 R, +6.8 R/month**
— better than the reported +0.374 R, because the 12h early exit costs
-0.037 R and is correctly OFF in the bot.

### Method 1 — Funding rate (+ open interest)
MEXC funding-rate history was fetched for all 15 pairs (1500 points
each, back to ~Jun 2025; TON only back to ~Feb 27, 2026, 1547 points
at 4h intervals since TON settles every 4h). Coverage 1013/1015 matched
trades (99.8%). Funding distribution: median +0.00004, p90 +0.00010,
p99 +0.00020 per 8h. **Open-interest HISTORY is NOT obtainable**: the
MEXC OI endpoint is blocked by its WAF (Access Denied) and Binance is
geo-blocked from the sandbox, so only the funding leg was tested, NOT
funding+OI. Absolute thresholds of +/-0.05% and +/-0.1% never fire
(funding never got that extreme), so percentile and lower absolute
thresholds were used instead.
- Percentile filter (skip LONG when funding >= 90th percentile of the
  trailing 30d, skip SHORT when <= 10th), all trades: kept n=768,
  41.8% win, +0.011 R; **skipped n=247, 43.3% win, +0.038 R — the
  skipped trades were BETTER**, so the filter does not help on all
  trades.
- Absolute thresholds: trades with funding beyond +/-0.0001 won
  **48.3% at +0.168 R** (n=58) vs +0.009 R for the rest; beyond
  +/-0.00015 they won **59.3% at +0.204 R** (n=27). The most
  extreme-funding trades are the BEST, not the worst — the opposite of
  the "crowded trades underperform" hypothesis. High funding coincides
  with strong trends, and a trend-following bot does well in strong
  trends.
- On the V3.1 selection the percentile filter gives +0.501 R (n=146)
  vs +0.411 R without it, but out-of-sample it is weak: Jan-Jun it
  helps (+0.775 vs +0.591 R) and Jul-Nov it barely helps (+0.309 vs
  +0.285 R) while monthly return FALLS (+5.3 vs +6.2 R/month, fewer
  trades). On all trades out-of-sample it HURTS in Jul-Nov (-0.032 vs
  +0.001 R).
- **Verdict: DO NOT ADOPT.** The evidence is mixed/contradictory, the
  effect is small, and the absolute-threshold test shows the premise is
  backwards for a trend-following bot. Do not skip high-funding trades.

### Method 2 — Partial take-profits
Take half off at +1.0R (or +0.8R), let the rest run to the 1.8R target
or the 24h time-stop. Simulated on 60m price paths (partial level
reached in 78.5% of trades at +1.0R, 82.4% at +0.8R). Verified by hand
on one trade of each kind (TARGET_HIT partial +1R = exactly 1.400 R;
STOP_HIT with no partial before the stop = -1.000 R; TIME_STOP
+0.782 R with partial +1R = +0.891 R).
- On the V3.1 selection: partial +1.0R (trail off) 52.5% win, +0.268 R;
  +1.0R (trail on) **55.2% win, +0.235 R**; +0.8R (trail off) 53.0%
  win, +0.263 R; +0.8R (trail on) **62.8% win, +0.291 R**. All beat
  V3.1's 45.9% win rate but ALL are below V3.1's +0.411 R.
- On ALL matched trades (no filters): +1.0R gives 43.9% win, **-0.014 R**;
  +0.8R gives 45.2% win, **-0.011 R** — both make unfiltered expectancy
  NEGATIVE (baseline +0.018 R).
- Out-of-sample (V3.1 selection, +1.0R trail on): Jan-Jun win rate
  56.0% -> 65.3% but avg R +0.516 -> +0.421 R; **Jul-Nov win rate
  48.1% -> 48.1% (NO lift) and avg R +0.265 -> +0.106 R**. The
  win-rate benefit does not hold in the holdout.
- **Verdict: DO NOT ADOPT.** Partial TP lifts win rate (up to 62.8%)
  but LOWERS average R and monthly return in every test — it trades
  expectancy for win rate, and the win-rate lift vanishes
  out-of-sample. If win rate is ever valued over expectancy (e.g. for
  psychology / smaller drawdowns), +0.8R with the trailing stop is the
  variant to use, at a cost of ~0.12 R/trade.

### Method 3 — Better regime detection
ATR percentile (BTC daily ATR(14) vs trailing 90 days) and daily ADX,
from the BTC daily klines already in `channel-analysis/klines/`.
- ATR percentile [0.20, 0.80] (normal vol only), all trades: 48.3% win,
  **+0.195 R** (n=437); [0.25, 0.75]: 50.0% win, **+0.240 R** (n=384);
  [0.10, 0.90]: +0.146 R. ATR pct >= 0.20 (skip compressed): +0.142 R;
  ATR pct <= 0.80 (skip extreme): +0.034 R.
- Daily ADX >= 20: +0.049 R (weak); daily ADX >= 25: +0.132 R (n=518).
- In the V3.1 pipeline (selection + trailing BE): **ATR pct
  [0.20, 0.80] REPLACING the 50DMA: n=138, 52.9% win, +0.560 R** —
  beats the 50DMA version (+0.411 R) on win rate, avg R and monthly
  return (~+7.0 vs +6.8 R/month). Daily ADX >= 25 only: +0.443 R.
  **50DMA AND ATR pct [0.20, 0.80]: n=83, 51.8% win, +0.621 R** (best
  in-sample avg R), but out-of-sample it falls to +0.381 R / 41.9% win
  in Jul-Nov (monthly +3.3), so it is NOT adopted.
- Out-of-sample, ATR alone HOLDS UP: [0.20, 0.80] Jan-Jun +0.696 R
  (54.4% win, +7.9 R/month), Jul-Nov +0.465 R (51.9% win,
  +7.5 R/month). [0.25, 0.75]: Jan-Jun +0.807 R, Jul-Nov +0.474 R.
- **April 2026 is NOT fixed by any rule.** April all matched: 24.4%
  win, -0.455 R. April ATR pct [0.20, 0.80]: 8.0% win, -0.798 R.
  April daily ADX >= 25: 34.2% win, -0.346 R (best April figure, still
  bad). May is fixed by daily ADX >= 25 (+0.037 R, 46.8% win). April
  remains genuinely untradeable chop under every rule tested.
- **Verdict: ADOPT the ATR-percentile filter [0.20, 0.80] REPLACING
  the 50DMA regime filter.** It is the strongest, most robust regime
  improvement. Daily ADX >= 25 is a useful secondary check but adds
  little on top of ATR and is not adopted as a separate rule.

### Combined V3.2 (all three methods stacked on V3.1)
50DMA + daily ADX >= 20 + funding percentile filter + top-6 + ADX
rising + 12h cooldown + partial TP +1R + trailing BE: in-sample n=99,
**61.6% win, +0.346 R, +3.1 R/month**; Jan-Jun n=54, 70.4% win,
+0.532 R; Jul-Nov n=45, 51.1% win, +0.122 R. The same selection
WITHOUT partial TP: n=99, 49.5% win, 28.3% loss, 22 breakevens,
**+0.554 R** — better expectancy than V3.1's +0.411 R, but monthly
return is lower (fewer trades). **The kitchen-sink combined (+0.346 R)
is WORSE than V3.1 (+0.411 R) on expectancy and monthly return,
despite the highest win rate (61.6%).** Stacking filters is not
better; the selection filters help expectancy, but partial TP drags it
back down.

### Recommendation (V3.2)
- **Recommended V3.2 (implemented in `bot_v3_2.py`):** V3.1 with the
  50DMA regime filter REPLACED by the ATR-percentile filter
  [0.20, 0.80]; keep top-6, ADX rising (60m), 12h post-loss cooldown,
  trailing stop to breakeven at +0.8R, rebuilt PREMIUM label.
  Backtest: **138 trades, 52.9% win, +0.560 R/trade, ~12.5
  signals/month, ~+7.0 R/month** (vs V3.1: 183 trades, 45.9% win,
  +0.411 R, ~+6.8 R/month; vs V3.0: 42.2% win, +0.018 R). This beats
  V3.1 on win rate, avg R and monthly return, and holds up
  out-of-sample in both halves.
- **Do NOT adopt:** the funding filter (mixed, premise backwards) or
  partial take-profits (lifts win rate, cuts expectancy, no
  out-of-sample win-rate lift). Both are implemented as OFF flags in
  `bot_v3_2.py` (`V32_FUNDING_FILTER=False`, `V32_PARTIAL_TP_R=0.0`)
  so they are not live. The 50DMA filter is available as an option
  (`V32_USE_50DMA=False` by default).
- **Honesty note:** all V3.2 numbers are in-sample except where the
  Jan-Jun / Jul-Nov split is stated; the +0.560 R and the combined
  +0.554 R are in-sample and likely optimistic. April remains a losing
  month under every rule tested. Do NOT deploy with real money on this
  backtest alone; forward-test the V3.2 rules on live signals first,
  and do not push to GitHub without Anthony's explicit approval.
- **Files:** `bot_v3_2.py` (ATR regime replaces 50DMA; funding and
  partial TP off by default), `test_v3_2.py` (16 tests, all passing),
  `backtest_v3_2.py`, `fetch_funding.py`,
  `channel-analysis/funding/` (15 JSON files, MEXC funding history),
  `channel-analysis/v3_2-report.txt`. `test_v3_1.py` (21 tests) still
  passes unchanged.

### Adopted (Nov 11, 2026) — V3.2 is the current version

Anthony adopted **only the working part of V3.2: the ATR-percentile
regime filter [0.20, 0.80] replacing the 50DMA**. Verified in
`bot_v3_2.py`: `V32_ATR_REGIME=True`, `V32_ATR_LO=0.20`,
`V32_ATR_HI=0.80`, `V32_USE_50DMA=False` (so `V31_REGIME_FILTER` is
off), `V32_FUNDING_FILTER=False`, `V32_PARTIAL_TP_R=0.0`. SL 1.25x
ATR(4h) and R:R 1:1.8 unchanged. Tests re-run on adoption:
`test_v3_2.py` 16 passed, 0 failed; `test_v3_1.py` 21 passed,
0 failed. **Funding and partial take-profits stay OFF** — both were
tested and rejected (funding: premise backwards; partial TPs: win rate
up, expectancy down, no out-of-sample lift). The 50DMA filter remains
available as an option (`V32_USE_50DMA=True`) but is off by default.
Equity from $1,000 (bot's own per-trade risk, compounding, as of
09:00 WAT 11 Nov 2026): see `channel-analysis/equity-1000usd.txt`
(V3.0 $1,063.49, V3.1 $3,387.60, V3.2 $3,769.99). Local only — not
pushed to GitHub.
