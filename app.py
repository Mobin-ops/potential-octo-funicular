import time
import requests
import threading
from flask import Flask, jsonify
from telegram import Bot
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import pandas as pd

app = Flask(__name__)
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
TELEGRAM_CHANNEL_ID = '@AutoTradeCrypt1'
BINANCE_API_KEY = 'YOUR_BINANCE_API_KEY'
BINANCE_SECRET = 'YOUR_BINANCE_SECRET'
SYMBOL = 'ETHUSDT'
INTERVAL = '15m'
TP_LEVELS = [1.02, 1.04, 1.06]
SL_FACTOR = 0.98
active_signal = None

def get_klines(symbol, interval, limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'])
    df['close'] = df['close'].astype(float)
    return df

def generate_signal(df):
    ema_fast = EMAIndicator(df['close'], window=9).ema_indicator()
    ema_slow = EMAIndicator(df['close'], window=21).ema_indicator()
    rsi = RSIIndicator(df['close'], window=14).rsi()
    if ema_fast.iloc[-2] < ema_slow.iloc[-2] and ema_fast.iloc[-1] > ema_slow.iloc[-1] and rsi.iloc[-1] > 50:
        return 'buy'
    return None

def send_signal(bot, entry):
    tp1 = round(entry * TP_LEVELS[0], 4)
    tp2 = round(entry * TP_LEVELS[1], 4)
    tp3 = round(entry * TP_LEVELS[2], 4)
    sl = round(entry * SL_FACTOR, 4)
    msg = f"""
📢 [Auto Signal - Trend Strategy]
🪙 Symbol: {SYMBOL}
🎯 Entry: {entry}
📈 TP1: {tp1}
📈 TP2: {tp2}
📈 TP3: {tp3}
🛑 SL: {sl}
⏰ Time: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=msg)
    return {'entry': entry, 'tp': [tp1, tp2, tp3], 'sl': sl, 'hit': []}

def monitor_targets(bot, signal):
    price = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}").json()['price'])
    if price <= signal['sl'] and 'sl' not in signal['hit']:
        bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=f"❌ {SYMBOL} hit SL ({signal['sl']})")
        signal['hit'].append('sl')
    for i, tp in enumerate(signal['tp']):
        if price >= tp and f'tp{i+1}' not in signal['hit']:
            bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=f"✅ {SYMBOL} hit TP{i+1} ({tp})")
            signal['hit'].append(f'tp{i+1}')
    return signal

def run_bot():
    global active_signal
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    while True:
        try:
            if not active_signal:
                df = get_klines(SYMBOL, INTERVAL)
                signal = generate_signal(df)
                if signal == 'buy':
                    entry_price = df['close'].iloc[-1]
                    active_signal = send_signal(bot, entry_price)
            else:
                active_signal = monitor_targets(bot, active_signal)
                if len(active_signal['hit']) >= 4:
                    active_signal = None
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60)

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

@app.route('/')
def home():
    return jsonify({"message": "Trading bot is running!", "symbol": SYMBOL})

@app.route('/status')
def status():
    return jsonify({"active_signal": active_signal, "symbol": SYMBOL})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
