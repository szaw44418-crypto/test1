import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Server ကို Background မှာ အလုပ်လုပ်ခိုင်းရန်
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


import os
import time
import ccxt
import pandas as pd
import pandas_ta as ta
import requests

API_KEY = 'zbUldORQgWXXn7Zv4WXBSHaCdaMv2aFXu7poayG7AdVHYIm2x9eVRYSwT2Yw5D2Y'
SECRET_KEY = 'YnwxL4v30mOaf8m5UamkKXm4ZArdOlB60etu5M2BfWItEhV1MFTTnhyAk6sOWTb6'
TELEGRAM_TOKEN = '8849579856:AAF7kWMMgtCswjY-Vcog-oa0ur16c60dJio'
CHAT_ID = '6127362073'

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
exchange.set_sandbox_mode(True)

symbol = 'BNB/USDT'
timeframe = '1h'

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = f"🤖 Bot စတင်အလုပ်လုပ်နေပါပြီ ({symbol})..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['RSI'] = ta.rsi(df['close'], length=14)
            macd = ta.macd(df['close'])
            df = pd.concat([df, macd], axis=1)
            
            current_rsi = df['RSI'].iloc[-1]
            macd_hist = df['MACDh_12_26_9'].iloc[-1]
            
            print(f"စစ်ဆေးနေစဉ်... RSI: {current_rsi:.2f}, MACD Hist: {macd_hist:.4f}")
            
            if current_rsi < 30 and macd_hist > 0:
                msg = f"🚨 အဝယ်အချက်ပြမှု (Oversold & Bullish) တွေ့ရှိပါပြီ! RSI: {current_rsi:.2f}"
                send_telegram_message(msg)
            elif current_rsi > 70:
                msg = f"⚠️ အရောင်းအချက်ပြမှု (Overbought) တွေ့ရှိပါပြီ! RSI: {current_rsi:.2f}"
                send_telegram_message(msg)
                
            time.sleep(3600)
        except Exception as e:
            err_msg = f"❌ Bot အမှားအယွင်း ဖြစ်ပေါ်သည်: {e}"
            send_telegram_message(err_msg)
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
