import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pandas as pd
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

trading_exchange = ccxt.binance({
    'apiKey': SPOT_API_KEY,
    'secret': SPOT_SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
trading_exchange.set_sandbox_mode(True)

coins = [
    "XRP/USDT",
    "DOGE/USDT",
    "TRX/USDT",
    "LINK/USDT",
    "AVAX/USDT",
    "SUI/USDT",
    "PEPE/USDT"
]

bot_states = {
    symbol: {
        "in_position": False,
        "buy_price": 0.0,
        "usdt_amount": 10.0,
        "purchased_amount": 0.0,
        "target_profit_pct": 0.015,
        "stop_loss_pct": 0.01
    } for symbol in coins
}

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram ပို့ရာတွင် အမှားအယွင်းရှိသည်: {e}")

def run_bot():
    start_msg = "🤖 Fast Trading Bot (Instant Execution) စတင်အလုပ်လုပ်နေပါပြီ..."
    print(start_msg)
    send_telegram_message(start_msg)
    
    price_history = {symbol: [] for symbol in coins}

    while True:
        for symbol in coins:
            bot_state = bot_states[symbol]
            
            try:
                ticker = trading_exchange.fetch_ticker(symbol)
                current_price = float(ticker['last'])
                
                price_history[symbol].append(current_price)
                if len(price_history[symbol]) > 10:
                    price_history[symbol].pop(0)
                
                # ဒေတာ ၅ ခုပြည့်သည်နှင့် ချက်ချင်း စတင်မည်
                if len(price_history[symbol]) < 5:
                    print(f"[{symbol}] ဈေးနှုန်း: {current_price} | ဒေတာ စုဆောင်းနေဆဲ ({len(price_history[symbol])}/5)...")
                    continue
                
                prices = pd.Series(price_history[symbol])
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=3).mean().iloc[-1]
                loss = (-delta.where(delta < 0, 0)).rolling(window=3).mean().iloc[-1]
                
                if pd.isna(gain) or pd.isna(loss) or loss == 0:
                    rsi = 50.0
                else:
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                
                print(f"[{symbol}] ဈေးနှုန်း: {current_price} | RSI: {rsi:.2f} | Position: {bot_state['in_position']}")
                
                if not bot_state["in_position"]:
                    if rsi < 55:  # ဝယ်ယူရန် အခြေအနေ
                        try:
                            raw_amount = bot_state["usdt_amount"] / current_price
                            formatted_amount = trading_exchange.amount_to_precision(symbol, raw_amount)
                            
                            order = trading_exchange.create_order(symbol, 'market', 'buy', float(formatted_amount), None, {'quoteOrderQty': bot_state["usdt_amount"]})
                            
                            filled_amount = float(order.get('filled', float(formatted_amount)))
                            actual_price = float(order.get('average', current_price))
                            
                            bot_state["in_position"] = True
                            bot_state["buy_price"] = actual_price
                            bot_state["purchased_amount"] = filled_amount
                            
                            msg = f"🟢 **[{symbol} Cycle စတင်ခြင်း]**\n💰 သုံးစွဲငွေ: {bot_state['usdt_amount']} USDT\n📥 ဝယ်ဈေး: {actual_price} USDT\n🪙 ရရှိလာသည့်ပမာဏ: {filled_amount}\n🔹 RSI: {rsi:.2f}"
                            send_telegram_message(msg)
                        except Exception as buy_err:
                            print(f"[{symbol}] Buy Error: {buy_err}")
                else:
                    buy_price = bot_state["buy_price"]
                    profit_pct = (current_price - buy_price) / buy_price
                    
                    print(f"[{symbol}] လက်ရှိ အမြတ်/အရှုံး: {profit_pct*100:.2f}%")
                    
                    if profit_pct >= bot_state["target_profit_pct"] or profit_pct <= -bot_state["stop_loss_pct"]:
                        try:
                            sell_amount = bot_state["purchased_amount"]
                            formatted_sell_amount = trading_exchange.amount_to_precision(symbol, sell_amount)
                            
                            order = trading_exchange.create_market_sell_order(symbol, float(formatted_sell_amount))
                            
                            earned_amount = (current_price - buy_price) * sell_amount
                            status_emoji = "🎉" if profit_pct > 0 else "⚠️"
                            
                            report_msg = (
                                f"{status_emoji} **[{symbol} Cycle ပြီးဆုံးခြင်း]**\n\n"
                                f"📥 ဝယ်ဈေး: {buy_price} USDT\n"
                                f"📤 ရောင်းဈေး: {current_price} USDT\n"
                                f"📈 ရာခိုင်နှုန်း: {profit_pct*100:+.2f}%\n"
                                f"💵 အမြတ်/အရှုံး: {earned_amount:+.2f} USDT"
                            )
                            send_telegram_message(report_msg)
                            
                            bot_state["in_position"] = False
                            bot_state["buy_price"] = 0.0
                            bot_state["purchased_amount"] = 0.0
                        except Exception as sell_err:
                            print(f"[{symbol}] Sell Error: {sell_err}")
                
            except Exception as coin_err:
                print(f"Error checking {symbol}: {coin_err}")

        time.sleep(5)

if __name__ == "__main__":
    run_bot()
