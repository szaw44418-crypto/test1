import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pandas as pd
import yfinance as yf
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

# Telegram Configuration
TELEGRAM_TOKEN = '8849579856:AAF7kWMMgtCswjY-Vcog-oa0ur16c60dJio'
CHAT_ID = '6127362073'

ticker_symbol = 'BNB-USD'

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = f"🤖 Bot စတင်အလုပ်လုပ်နေပါပြီ ({ticker_symbol} via Yahoo Finance)..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    while True:
        try:
            # multi_level_index=False ဖြင့် Single-level DataFrame ကို တိုက်ရိုက်ထုတ်ယူမည်
            df = yf.download(ticker_symbol, period="5d", interval="60m", progress=False, multi_level_index=False)
            
            if df.empty or len(df) < 30:
                print("⚠️ ဒေတာ အပြည့်အစုံ မရသေးပါ၊ ခေတ္တစောင့်ဆိုင်းနေပါသည်...")
                time.sleep(300)
                continue
                
            close_prices = pd.to_numeric(df['Close'], errors='coerce')
            
            # RSI တွက်ချက်ခြင်း
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # MACD တွက်ချက်ခြင်း
            exp1 = close_prices.ewm(span=12, adjust=False).mean()
            exp2 = close_prices.ewm(span=26, adjust=False).mean()
            macd_line = exp1 - exp2
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            
            current_rsi = rsi.iloc[-1]
            current_macd_hist = macd_hist.iloc[-1]
            
            if pd.isna(current_rsi) or pd.isna(current_macd_hist):
                print("⚠️ RSI သို့မဟုတ် MACD တန်ဖိုး NaN ဖြစ်နေပါသည်...")
                time.sleep(300)
                continue
            
            print(f"စစ်ဆေးနေစဉ်... RSI: {current_rsi:.2f}, MACD Hist: {current_macd_hist:.4f}")
            
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
            time.sleep(900)

if __name__ == "__main__":
    run_bot()
