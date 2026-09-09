import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import ccxt
import pandas as pd
import requests

# Render အတွက် Port ဖွင့်ပေးသော HTTP Server
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Server ကို Background တွင် စတင်ခြင်း
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# API Keys များနှင့် Configuration များ
API_KEY = 'zbUldORQgWXXn7Zv4WXBSHaCdaMv2aFXu7poayG7AdVHYIm2x9eVRYSwT2Yw5D2Y'
SECRET_KEY = 'YnwxL4v30mOaf8m5UamkKXm4ZArdOlB60etu5M2BfWItEhV1MFTTnhyAk6sOWTb6'
TELEGRAM_TOKEN = '8849579856:AAF7kWMMgtCswjY-Vcog-oa0ur16c60dJio'
CHAT_ID = '6127362073'

# Sandbox Mode ကို ဖြုတ်လိုက်ပြီး Live Public Market Data ကို တိုက်ရိုက်ယူမည်
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

symbol = 'BNB/USDT'
timeframe = '1h'

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = f"🤖 Bot စတင်အလုပ်လုပ်နေပါပြီ ({symbol})..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=200)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # ဒေတာများကို ဂဏန်းအမျိုးအစား (float) သို့ တိကျစွာပြောင်းလဲခြင်း
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            
            # RSI တွက်ချက်ခြင်း
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD တွက်ချက်ခြင်း
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd_line = exp1 - exp2
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            
            current_rsi = df['RSI'].iloc[-1]
            current_macd_hist = macd_hist.iloc[-1]
            
            # တန်ဖိုးများ NaN ဖြစ်နေခြင်း ရှိမရှိ စစ်ဆေးခြင်း
            if pd.isna(current_rsi) or pd.isna(current_macd_hist):
                print("⚠️ ဒေတာ အပြည့်အစုံ မရသေးပါ၊ ခေတ္တစောင့်ဆိုင်းနေပါသည်...")
                time.sleep(60)
                continue
            
            print(f"စစ်ဆေးနေစဉ်... RSI: {current_rsi:.2f}, MACD Hist: {current_macd_hist:.4f}")
            
            # အရောင်းအဝယ် အချက်ပြမှုများ စစ်ဆေးခြင်း
            if current_rsi < 30 and current_macd_hist > 0:
                msg = f"🚨 အဝယ်အချက်ပြမှု (Oversold & Bullish) တွေ့ရှိပါပြီ!\n📊 BNB / USDT\n🔹 RSI: {current_rsi:.2f}\n🔹 MACD Hist: {current_macd_hist:.4f}"
                send_telegram_message(msg)
            elif current_rsi > 70 and current_macd_hist < 0:
                msg = f"⚠️ အရောင်းအချက်ပြမှု (Overbought & Bearish) တွေ့ရှိပါပြီ!\n📊 BNB / USDT\n🔹 RSI: {current_rsi:.2f}\n🔹 MACD Hist: {current_macd_hist:.4f}"
                send_telegram_message(msg)
                
            time.sleep(3600)
            
        except Exception as e:
            err_msg = f"❌ Bot အမှားအယွင်း ဖြစ်ပေါ်သည်: {e}"
            print(err_msg)
            send_telegram_message(err_msg)
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
