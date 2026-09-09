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

symbol = 'BTC/USDT'
ticker_symbol = 'BTC-USD'

bot_state = {
    "in_position": False,
    "buy_price": 0.0,
    "usdt_amount": 10.0,      # 🛒 ဝယ်ယူမည့် USDT ပမာဏ (ဥပမာ - ၁၀ ဒေါ်လာဖိုး)
    "purchased_btc": 0.0,     # ဝယ်ယူရရှိလာသော BTC ပမာဏကို မှတ်ရန်
    "target_profit_pct": 0.015, # ၁.၅% အမြတ်ရလျှင် ရောင်းမည်
    "stop_loss_pct": 0.01      # ၁% ကျလျှင် Stop Loss လုပ်မည်
}

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = f"🤖 BTC Auto Profit Trading Bot (USDT Amount Mode) စတင်အလုပ်လုပ်နေပါပြီ ({symbol})..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    # ဈေးကွက်ဒေတာနှင့် ဒဿမတိကျမှု စည်းမျဉ်းများကို ကြိုတင်ရယူရန်
    try:
        exchange.load_markets()
    except Exception as e:
        print(f"Markets Load Error: {e}")

    while True:
        try:
            df = yf.download(ticker_symbol, period="5d", interval="60m", progress=False, multi_level_index=False)
            
            if df.empty or len(df) < 30:
                print("⚠️ ဒေတာ အပြည့်အစုံ မရသေးပါ...")
                time.sleep(300)
                continue
                
            close_prices = pd.to_numeric(df['Close'], errors='coerce')
            current_price = close_prices.iloc[-1]
            
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
            
            if not bot_state["in_position"]:
                if current_rsi < 50 or current_macd_hist > 0:
                    try:
                        # ဒဿမ error မတက်စေရန် ပမာဏကို ဈေးကွက်စည်းမျဉ်းအတိုင်း ညှိခြင်း
                        raw_amount = bot_state["usdt_amount"] / current_price
                        formatted_amount = exchange.amount_to_precision(symbol, raw_amount)
                        
                        # USDT ပမာဏဖြင့် Market Buy ဝယ်ယူခြင်း
                        order = exchange.create_order(symbol, 'market', 'buy', float(formatted_amount), None, {'quoteOrderQty': bot_state["usdt_amount"]})
                        
                        filled_amount = float(order.get('filled', float(formatted_amount)))
                        actual_price = float(order.get('average', current_price))
                        
                        bot_state["in_position"] = True
                        bot_state["buy_price"] = actual_price
                        bot_state["purchased_btc"] = filled_amount
                        
                        msg = f"🟢 **[BTC Cycle စတင်ခြင်း - USDT ဖြင့် အဝယ်အော်ဒါ]**\n📊 ဈေးကွက်: {symbol}\n💰 သုံးစွဲငွေ: {bot_state['usdt_amount']} USDT\n📥 ဝယ်ဈေး: {actual_price:.2f} USDT\n🪙 ရရှိလာသည့် BTC: {filled_amount:.6f}\n🔹 RSI: {current_rsi:.2f}"
                        send_telegram_message(msg)
                    except Exception as buy_err:
                        print(f"Buy Error: {buy_err}")
            else:
                buy_price = bot_state["buy_price"]
                profit_pct = (current_price - buy_price) / buy_price
                
                print(f"လက်ရှိ အမြတ်/အရှုံး ရာခိုင်နှုန်း: {profit_pct*100:.2f}%")
                
                if profit_pct >= bot_state["target_profit_pct"] or profit_pct <= -bot_state["stop_loss_pct"]:
                    try:
                        # ရောင်းချမည့်ပမာဏကို ဒဿမ error ကင်းစေရန် ထပ်မံညှိခြင်း
                        sell_amount = bot_state["purchased_btc"]
                        formatted_sell_amount = exchange.amount_to_precision(symbol, sell_amount)
                        
                        order = exchange.create_market_sell_order(symbol, float(formatted_sell_amount))
                        
                        earned_amount = (current_price - buy_price) * sell_amount
                        status_emoji = "🎉" if profit_pct > 0 else "⚠️"
                        
                        report_msg = (
                            f"{status_emoji} **[BTC Cycle ပြီးဆုံးခြင်း - Report အကျဉ်းချုပ်]**\n\n"
                            f"📊 ဈေးကွက်: {symbol}\n"
                            f"📥 ဝယ်ဈေး: {buy_price:.2f} USDT\n"
                            f"📤 ရောင်းဈေး: {current_price:.2f} USDT\n"
                            f"📈 ရာခိုင်နှုန်း: {profit_pct*100:+.2f}%\n"
                            f"💵 အမြတ်/အရှုံး: {earned_amount:+.2f} USDT"
                        )
                        send_telegram_message(report_msg)
                        
                        bot_state["in_position"] = False
                        bot_state["buy_price"] = 0.0
                        bot_state["purchased_btc"] = 0.0
                    except Exception as sell_err:
                        print(f"Sell Error: {sell_err}")

            time.sleep(1800)
            
        except Exception as e:
            err_msg = f"❌ Bot အမှားအယွင်း ဖြစ်ပေါ်သည်: {e}"
            print(err_msg)
            send_telegram_message(err_msg)
            time.sleep(900)

if __name__ == "__main__":
    run_bot()
