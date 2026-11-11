"""Fetch MEXC perpetual funding-rate history for all 15 TonyBot pairs.

Endpoint: GET https://contract.mexc.com/api/v1/contract/funding_rate/history
  ?symbol={SYM}_USDT&page_num=N&page_size=500
Returns newest-first pages; each row: {symbol, fundingRate, settleTime(ms),
collectCycle (hours), fundingType}. BTC/ETH settle every 8h; TON every 4h.

Saves one JSON per pair to channel-analysis/funding/{SYM}.json, as a list of
{settleTime, fundingRate} sorted ascending by settleTime. Fetches back to
2025-12-01 so there is a trailing window for the Jan 2026 signals.

Usage: /tmp/tonybot-test-venv/bin/python fetch_funding.py
"""
import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "channel-analysis", "funding")
os.makedirs(OUT, exist_ok=True)

PAIRS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "SUI", "TON",
         "LINK", "AVAX", "UNI", "NEAR", "LTC", "BNB"]
# fetch back to this timestamp (ms) so Jan 2026 signals have trailing history
CUTOFF_MS = 1764547200000  # 2025-12-01 00:00 UTC

HDRS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tonybot-research"}


def fetch_pair(sym, retries=3):
    rows = []
    page = 1
    while True:
        url = ("https://contract.mexc.com/api/v1/contract/funding_rate/history"
               f"?symbol={sym}_USDT&page_num={page}&page_size=500")
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=HDRS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.load(resp)
                break
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 * (attempt + 1))
        d = data.get("data", {})
        batch = d.get("resultList", [])
        if not batch:
            break
        rows.extend({"settleTime": r["settleTime"],
                     "fundingRate": r["fundingRate"]} for r in batch)
        total = d.get("totalCount", 0)
        # stop once we have rows older than the cutoff
        if min(r["settleTime"] for r in batch) < CUTOFF_MS:
            break
        if page * 500 >= total:
            break
        page += 1
        time.sleep(0.2)
    rows.sort(key=lambda r: r["settleTime"])
    return rows


def main():
    for sym in PAIRS:
        rows = fetch_pair(sym)
        path = os.path.join(OUT, f"{sym}.json")
        with open(path, "w") as f:
            json.dump(rows, f)
        if rows:
            print(f"{sym}: {len(rows)} funding points, "
                  f"{rows[0]['settleTime']} .. {rows[-1]['settleTime']}")
        else:
            print(f"{sym}: NO DATA")
        time.sleep(0.3)


if __name__ == "__main__":
    main()
