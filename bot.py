import ccxt
import pandas as pd
import pandas_ta as ta
import time
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv()  # reads variables from a local .env file (never committed)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError(
        "Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID. "
        "Copy .env.example to .env and fill in your own values."
    )

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'DOT/USDT', 'SUI/USDT', 'TON/USDT'
]
TIMEFRAME = '1h'
SIGNAL_COOLDOWN_HOURS = 4  # Prevent spamming the same signal

# --- 2. MEMORY STORAGE ---
active_trades = []
last_alert_time = {}
cooldowns = {}
exchange = ccxt.mexc()

# --- 3. HELPER FUNCTIONS ---
def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.get(url, params=params)
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

def fetch_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return pd.DataFrame()

def check_whale_activity(symbol):
    """
    Checks for massive trades (> $500k) in the last few minutes.
    Returns: "BUY", "SELL", or None.
    """
    try:
        trades = exchange.fetch_trades(symbol, limit=50)
        whale_buy_vol = 0
        whale_sell_vol = 0
        WHALE_THRESHOLD = 500000

        for trade in trades:
            cost = trade['cost']
            if cost >= WHALE_THRESHOLD:
                if trade['side'] == 'buy':
                    whale_buy_vol += cost
                    print(f"🐋 WHALE BUY: ${round(cost)} on {symbol}!")
                elif trade['side'] == 'sell':
                    whale_sell_vol += cost
                    print(f"🐻 WHALE DUMP: ${round(cost)} on {symbol}!")

        if whale_buy_vol > whale_sell_vol: return "BUY"
        elif whale_sell_vol > whale_buy_vol: return "SELL"
        else: return None
    except:
        return None

# --- 4. DATABASE FUNCTIONS ---
TRADES_FILE = "trades.json"

def load_trades():
    global active_trades
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                active_trades = json.load(f)
            print(f"📂 Loaded {len(active_trades)} active trades.")
        except Exception as e:
            print(f"⚠️ CRITICAL ERROR loading database: {e}")
            active_trades = []
    else:
        print("🆕 No database found. Starting fresh.")

def save_trades():
    try:
        with open(TRADES_FILE, "w") as f:
            json.dump(active_trades, f, indent=4)
    except Exception as e:
        print(f"❌ Error saving database: {e}")

# --- 5. CORE LOGIC ---
def analyze_market(symbol):
    # --- STEP 1: SAFETY CHECKS ---
    if symbol in cooldowns:
        if datetime.now() < cooldowns[symbol]:
            print(f"❄️ {symbol} is cooling down until {cooldowns[symbol].strftime('%H:%M')}. Skipping.")
            return
        else:
            del cooldowns[symbol]

    for trade in active_trades:
        if trade['symbol'] == symbol:
            return

    if symbol in last_alert_time:
        if datetime.now() - last_alert_time[symbol] < timedelta(hours=SIGNAL_COOLDOWN_HOURS):
            return

    df = fetch_data(symbol)
    if df.empty: return

    # --- STEP 2: CALCULATE MATH ---
    df['atr'] = df.ta.atr(length=14)
    df['rsi'] = df.ta.rsi(length=14)
    adx_df = df.ta.adx(length=14)
    df['adx'] = adx_df['ADX_14']
    df['ema_50'] = df.ta.ema(length=50)

    # --- BOLLINGER BANDS (Dynamic Support/Resistance) ---
    bbands = df.ta.bbands(length=20, std=2.0)

    # SAFETY CHECK: If the coin is new (not enough data), bbands might be empty.
    if bbands is None or bbands.empty:
        return

    # SAFE ACCESS: Get values by position (Column 0 = Lower, Column 2 = Upper)
    lower_band = bbands.iloc[-1, 0]
    upper_band = bbands.iloc[-1, 2]
    current_price = df['close'].iloc[-1]
    current_atr = df['atr'].iloc[-1]
    current_rsi = df['rsi'].iloc[-1]
    current_adx = df['adx'].iloc[-1]
    current_ema = df['ema_50'].iloc[-1]

    # --- STEP 3: WHALE RADAR ---
    whale_signal = check_whale_activity(symbol)

    signal = None
    trade_type = None
    strategy_name = ""

    # --- STRATEGY A: BOUNCE (Choppy Market) ---
    if current_adx < 30:
        rsi_limit = 50 if whale_signal == "BUY" else 45

        # BUY: Price touched the Lower Band (Oversold)
        if (current_price <= lower_band) and (current_rsi < rsi_limit):
            trade_type = "LONG"
            strategy_name = "Bounce"
            sl_price = current_price - (current_atr * 2)
            tp_price = current_price + ((current_price - sl_price) * 1.5)
            signal = True

        # SHORT: Price touched the Upper Band (Overbought)
        elif (current_price >= upper_band) and (current_rsi > 55):
            if whale_signal == "BUY":
                print(f"🛑 Blocking SHORT on {symbol}: Whales are buying!")
                return

            trade_type = "SHORT"
            strategy_name = "Bounce"
            sl_price = current_price + (current_atr * 2)
            tp_price = current_price - ((sl_price - current_price) * 1.5)
            signal = True

    # --- STRATEGY B: TREND (Fast Market) ---
    elif current_adx >= 30:
        if (current_price > current_ema) and (current_rsi < 70):
            trade_type = "LONG"
            strategy_name = "Trend"
            sl_price = current_price - (current_atr * 3)
            tp_price = current_price + ((current_price - sl_price) * 2.0)
            signal = True

        elif (current_price < current_ema) and (current_rsi > 30):
            if whale_signal == "BUY": return

            trade_type = "SHORT"
            strategy_name = "Trend"
            sl_price = current_price + (current_atr * 3)
            tp_price = current_price - ((sl_price - current_price) * 2.0)
            signal = True

    # --- EXECUTION ---
    if signal:
        last_alert_time[symbol] = datetime.now()
        new_trade = {
            'symbol': symbol, 'type': trade_type,
            'entry': current_price, 'tp': tp_price, 'sl': sl_price
        }
        active_trades.append(new_trade)
        save_trades()

        whale_msg = "🐋 *Whale Backed!*" if whale_signal else ""
        icon = "🚀" if strategy_name == "Trend" else "↩️"

        msg = (f"{icon} *{strategy_name.upper()} {trade_type}: {symbol}*\n"
               f"{whale_msg}\n"
               f"📊 ADX: {round(current_adx, 1)} (Mode: {strategy_name})\n"
               f"⚡ Entry: `{current_price}`\n"
               f"🎯 Target: `{round(tp_price, 6)}`\n"
               f"🛑 Stop: `{round(sl_price, 6)}`")
        send_telegram_alert(msg)
        print(f"✅ {strategy_name} Alert sent for {symbol}")

def track_active_trades():
    if not active_trades: return
    print(f"--- Tracking {len(active_trades)} Active Trades ---")

    for trade in active_trades[:]:
        try:
            ticker = exchange.fetch_ticker(trade['symbol'])
            current_price = ticker['last']

            # LONG LOGIC
            if trade['type'] == "LONG":
                if current_price >= trade['tp']:
                    send_telegram_alert(f"💰 WIN: {trade['symbol']}\n💸 Profit Secured!\n💤 Cooling down 30 mins.")
                    active_trades.remove(trade)
                    save_trades()
                    cooldowns[trade['symbol']] = datetime.now() + timedelta(minutes=30)

                elif current_price <= trade['sl']:
                    send_telegram_alert(f"❌ LOSS: {trade['symbol']}\n💀 Stop Hit.\n❄️ Cooling down 1 hour.")
                    active_trades.remove(trade)
                    save_trades()
                    cooldowns[trade['symbol']] = datetime.now() + timedelta(hours=1)

            # SHORT LOGIC
            elif trade['type'] == "SHORT":
                if current_price <= trade['tp']:
                    send_telegram_alert(f"💰 WIN: {trade['symbol']}\n💸 Profit Secured!\n💤 Cooling down 30 mins.")
                    active_trades.remove(trade)
                    save_trades()
                    cooldowns[trade['symbol']] = datetime.now() + timedelta(minutes=30)

                elif current_price >= trade['sl']:
                    send_telegram_alert(f"❌ LOSS: {trade['symbol']}\n💀 Stop Hit.\n❄️ Cooling down 1 hour.")
                    active_trades.remove(trade)
                    save_trades()
                    cooldowns[trade['symbol']] = datetime.now() + timedelta(hours=1)
        except:
            continue

def send_summary():
    if not active_trades: return
    msg = "📊 *4-HOUR REPORT* 📊\n\n"
    for trade in active_trades:
        try:
            df = fetch_data(trade['symbol'])
            current_price = df['close'].iloc[-1]
            if trade['type'] == "LONG":
                pnl = ((current_price - trade['entry']) / trade['entry']) * 100
            else:
                pnl = ((trade['entry'] - current_price) / trade['entry']) * 100
            icon = "🟢" if pnl > 0 else "🔴"
            msg += f"{icon} *{trade['symbol']}*: {round(pnl, 2)}%\n"
        except: continue
    send_telegram_alert(msg)

last_summary_time = datetime.now()

def job():
    global last_summary_time
    print(f"--- Scanning Market {datetime.now().strftime('%H:%M:%S')} ---")
    for pair in PAIRS:
        analyze_market(pair)
        time.sleep(1)
    track_active_trades()
    if datetime.now() - last_summary_time > timedelta(hours=4):
        send_summary()
        last_summary_time = datetime.now()

if __name__ == "__main__":
    print("🤖 Agent Starting...")
    load_trades()
    send_telegram_alert("🤖 *Bot is active!!*")
    time.sleep(2)
    send_summary()
    while True:
        job()
        time.sleep(60)
