import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pandas as pd
import yfinance as yf
import ccxt
import requests

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Trading Bot is running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

TELEGRAM_TOKEN = '8849579856:AAF7kWMMgtCswjY-Vcog-oa0ur16c60dJio'
CHAT_ID = '6127362073'

SPOT_API_KEY = os.environ.get("SPOT_API_KEY", "EGMDZzNYcF8aHKsKGxWurbK63sLFdKA42cDEZC3zd8IPkyD3JDEH7btCt4D34aWV")
SPOT_SECRET_KEY = os.environ.get("SPOT_SECRET_KEY", "YfGOumNKz4MMbZ9MBy7aMB3R6CWxSjVljJvreup8k3BGL5pi1pqc73ieCpOghM8R")

exchange = ccxt.binance({
    'apiKey': SPOT_API_KEY,
    'secret': SPOT_SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
exchange.set_sandbox_mode(True)

symbol = 'BNB/USDT'
ticker_symbol = 'BNB-USD'

# Bot State Management (Cycle ထိန်းချုပ်ရန်)
bot_state = {
    "in_position": False,
    "buy_price": 0.0,
    "amount": 0.05,
    "target_profit_pct": 0.02, # ၂% အမြတ်ရလျှင် ရောင်းမည်
    "stop_loss_pct": 0.015     # ၁.၅% ကျလျှင် Stop Loss လုပ်မည်
}

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = f"🤖 Auto Profit Trading Bot စတင်အလုပ်လုပ်နေပါပြီ ({symbol})..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    while True:
        try:
            df = yf.download(ticker_symbol, period="5d", interval="60m", progress=False, multi_level_index=False)
            
            if df.empty or len(df) < 30:
                print("⚠️ ဒေတာ အပြည့်အစုံ မရသေးပါ...")
                time.sleep(300)
                continue
                
            close_prices = pd.to_numeric(df['Close'], errors='coerce')
            current_price = close_prices.iloc[-1]
            
            # RSI & MACD တွက်ချက်ခြင်း
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss)))
            
            macd_line = close_prices.ewm(span=12, adjust=False).mean() - close_prices.ewm(span=26, adjust=False).mean()
            macd_hist = macd_line - macd_line.ewm(span=9, adjust=False).mean()
            
            current_rsi = rsi.iloc[-1]
            current_macd_hist = macd_hist.iloc[-1]
            
            if pd.isna(current_rsi) or pd.isna(current_macd_hist):
                time.sleep(300)
                continue
            
            print(f"ဈေးနှုန်း: {current_price:.2f} | RSI: {current_rsi:.2f} | MACD Hist: {current_macd_hist:.4f} | Position: {bot_state['in_position']}")
            
            # အကယ်၍ ပစ္စည်း မဝယ်ရသေးလျှင် (Position မရှိသေးလျှင်) အချက်ပြမှုစောင့်မည်
            if not bot_state["in_position"]:
                if current_rsi < 35 or current_macd_hist > 0: # အချက်ပြမှု အနည်းငယ် လွယ်ကူအောင် ညှိထားသည်
                    try:
                        order = exchange.create_market_buy_order(symbol, bot_state["amount"])
                        bot_state["in_position"] = True
                        bot_state["buy_price"] = current_price
                        
                        msg = f"🟢 **[Cycle စတင်ခြင်း - အဝယ်အော်ဒါ]**\n📊 ဈေးကွက်: {symbol}\n💰 ဝယ်ဈေး: {current_price:.2f} USDT\n🔹 RSI: {current_rsi:.2f}"
                        send_telegram_message(msg)
                    except Exception as buy_err:
                        print(f"Buy Error: {buy_err}")
            
            # အကယ်၍ ပစ္စည်းဝယ်ပြီးသား ဖြစ်နေလျှင် အမြတ်ထုတ်ရန် (Take Profit) သို့မဟုတ် Stop Loss စစ်မည်
            else:
                buy_price = bot_state["buy_price"]
                profit_pct = (current_price - buy_price) / buy_price
                
                print(f"လက်ရှိ အမြတ်/အရှုံး ရာခိုင်နှုန်း: {profit_pct*100:.2f}%")
                
                # Take Profit (သို့) Stop Loss ရောက်ရှိပါက ရောင်းချမည်
                if profit_pct >= bot_state["target_profit_pct"] or profit_pct <= -bot_state["stop_loss_pct"]:
                    try:
                        order = exchange.create_market_sell_order(symbol, bot_state["amount"])
                        
                        # Report ထုတ်ရန် တွက်ချက်ခြင်း
                        earned_amount = (current_price - buy_price) * bot_state["amount"]
                        status_emoji = "🎉" if profit_pct > 0 else "⚠️"
                        
                        report_msg = (
                            f"{status_emoji} **[Cycle ပြီးဆုံးခြင်း - Report အကျဉ်းချုပ်]**\n\n"
                            f"📊 ဈေးကွက်: {symbol}\n"
                            f"📥 ဝယ်ဈေး: {buy_price:.2f} USDT\n"
                            f"📤 ရောင်းဈေး: {current_price:.2f} USDT\n"
                            f"📈 ရာခိုင်နှုန်း: {profit_pct*100:+.2f}%\n"
                            f"💵 အမြတ်/အရှုံး: {earned_amount:+.2f} USDT"
                        )
                        send_telegram_message(report_msg)
                        
                        # State ကို ပြန်လည် Reset လုပ်မည်
                        bot_state["in_position"] = False
                        bot_state["buy_price"] = 0.0
                    except Exception as sell_err:
                        print(f"Sell Error: {sell_err}")

            time.sleep(1800) # မိနစ် ၃၀ လျှင် တစ်ကြိမ် စစ်ဆေးမည် (အမြတ်အစွန်း ပိုမိုဖမ်းဆီးနိုင်ရန်)
            
        except Exception as e:
            err_msg = f"❌ Bot အမှားအယွင်း ဖြစ်ပေါ်သည်: {e}"
            print(err_msg)
            send_telegram_message(err_msg)
            time.sleep(900)

if __name__ == "__main__":
    run_bot()
