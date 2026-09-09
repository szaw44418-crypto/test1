import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pandas as pd
import yfinance as yf
import ccxt
import requests

# Render အတွက် Port ဖွင့်ပေးသော HTTP Server
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Testnet Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Telegram Configuration
TELEGRAM_TOKEN = '8849579856:AAF7kWMMgtCswjY-Vcog-oa0ur16c60dJio'
CHAT_ID = '6127362073'

# 🔑 Binance Testnet Spot API Keys
SPOT_API_KEY = os.environ.get("SPOT_API_KEY", "EGMDZzNYcF8aHKsKGxWurbK63sLFdKA42cDEZC3zd8IPkyD3JDEH7btCt4D34aWV")
SPOT_SECRET_KEY = os.environ.get("SPOT_SECRET_KEY", "YfGOumNKz4MMbZ9MBy7aMB3R6CWxSjVljJvreup8k3BGL5pi1pqc73ieCpOghM8R")

exchange = ccxt.binance({
    'apiKey': SPOT_API_KEY,
    'secret': SPOT_SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# Binance Spot Testnet (Sandbox Mode) သို့ ချိတ်ဆက်ခြင်း
exchange.set_sandbox_mode(True)

symbol = 'BNB/USDT'
ticker_symbol = 'BNB-USD'

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = f"🤖 Testnet Spot Auto Trading Bot စတင်အလုပ်လုပ်နေပါပြီ ({symbol})..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    while True:
        try:
            # IP Ban ရှောင်ရှားရန် Yahoo Finance မှ ဈေးကွက်ဒေတာကို ယူမည်
            df = yf.download(ticker_symbol, period="5d", interval="60m", progress=False, multi_level_index=False)
            
            if df.empty or len(df) < 30:
                print("⚠️ ဒေတာ အပြည့်အစုံ မရသေးပါ...")
                time.sleep(300)
                continue
                
            close_prices = pd.to_numeric(df['Close'], errors='coerce')
            
            # RSI တွက်ချက်ခြင်း
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss)))
            
            # MACD တွက်ချက်ခြင်း
            macd_line = close_prices.ewm(span=12, adjust=False).mean() - close_prices.ewm(span=26, adjust=False).mean()
            macd_hist = macd_line - macd_line.ewm(span=9, adjust=False).mean()
            
            current_rsi = rsi.iloc[-1]
            current_macd_hist = macd_hist.iloc[-1]
            
            if pd.isna(current_rsi) or pd.isna(current_macd_hist):
                print("⚠️ RSI သို့မဟုတ် MACD တန်ဖိုး NaN ဖြစ်နေပါသည်...")
                time.sleep(300)
                continue
            
            print(f"စစ်ဆေးနေစဉ်... RSI: {current_rsi:.2f}, MACD Hist: {current_macd_hist:.4f}")
            
            # အဝယ်အချက်ပြမှု (Oversold & Bullish)
            if current_rsi < 30 and current_macd_hist > 0:
                msg = f"🚨 [TESTNET SPOT] အဝယ်အချက်ပြမှု တွေ့ရှိပါပြီ!\n📊 {symbol}\n🔹 RSI: {current_rsi:.2f}\n🔹 MACD Hist: {current_macd_hist:.4f}"
                send_telegram_message(msg)
                
                try:
                    # Testnet ပေါ်တွင် Test Order (Market Buy) တင်ခြင်း (ဥပမာ - 0.05 BNB)
                    amount_to_buy = 0.05 
                    order = exchange.create_market_buy_order(symbol, amount_to_buy)
                    
                    success_msg = f"✅ Testnet အဝယ်အော်ဒါ အောင်မြင်ပါသည်!\nOrder ID: {order.get('id')}"
                    print(success_msg)
                    send_telegram_message(success_msg)
                except Exception as order_err:
                    err_order_msg = f"❌ Order တင်ရာတွင် အမှားအယွင်းရှိသည်: {order_err}"
                    print(err_order_msg)
                    send_telegram_message(err_order_msg)

            time.sleep(3600)
            
        except Exception as e:
            err_msg = f"❌ Bot အမှားအယွင်း ဖြစ်ပေါ်သည်: {e}"
            print(err_msg)
            send_telegram_message(err_msg)
            time.sleep(900)

if __name__ == "__main__":
    run_bot()
