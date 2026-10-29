from flask import Flask
import threading
import requests
import finnhub
import yfinance as yf
from datetime import datetime, timedelta
import time
import os
import sys

app = Flask(__name__)

# ==========================================
# 1. الإعدادات الأساسية
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "9148905124:AAGIuJ7ZbI4LSaVVtFpnboVwXXB3zNd2CNg")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "5490419100")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "dbguue9r01qjpoc3bgogdbguue9r01qjpoc3bgp0")

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

# قائمة أسهم نشطة (البوت راح يفحصها كلها بدون ما ينحظر)
WATCHLIST = [
    'SOFI', 'MARA', 'RIOT', 'SNDL', 'TLRY', 'PLUG', 'FCEL', 'CLOV', 
    'WKHS', 'BBAI', 'SPCE', 'OPEN', 'CHPT', 'LCID', 'NIO', 'MULN', 
    'FFIE', 'SNAP', 'AMD', 'TSLA', 'NVDA', 'AAPL', 'PLTR', 'COIN'
]

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}", file=sys.stderr, flush=True)

def scan_stocks():
    print(f"\n⏳ [{datetime.now().strftime('%H:%M:%S')}] جاري فحص قائمة الأسهم...", file=sys.stderr, flush=True)
    
    for ticker in WATCHLIST:
        try:
            # جلب بيانات 5 دقائق لحساب RSI و VWAP
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="5m")
            
            if hist.empty or len(hist) < 15:
                continue
                
            current_price = hist['Close'].iloc[-1]
            closes = hist['Close'].tolist()
            
            # حساب RSI
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else 0
            avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            # حساب VWAP
            typical_prices = (hist['High'] + hist['Low'] + hist['Close']) / 3
            vwap = (typical_prices * hist['Volume']).cumsum().iloc[-1] / hist['Volume'].cumsum().iloc[-1]
            
            # شروط الدخول (السعر أقل من 20$، فوق VWAP، ومؤشر RSI بين 50 و 70)
            if (0.50 <= current_price <= 20.00 and 
                current_price > vwap and 
                50 <= rsi <= 70):
                
                # جلب الخبر من Finnhub
                news = finnhub_client.company_news(ticker, _from=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), to=datetime.now().strftime('%Y-%m-%d'))
                latest_news = news[0]['headline'] if news else "لا توجد أخبار حديثة"
                
                stop_loss = min(vwap, hist['Low'].tail(3).min()) * 0.99 
                target_1 = current_price * 1.05
                target_2 = current_price * 1.10
                
                alert_msg = (
                    f"🎯 <b>فرصة: {ticker}</b> 🎯\n\n"
                    f"💵 <b>السعر:</b> ${current_price:.2f}\n"
                    f"⚡ <b>RSI:</b> {rsi:.1f}\n"
                    f"🌊 <b>فوق VWAP:</b> نعم (${vwap:.2f})\n"
                    f"📰 <b>الخبر:</b> {latest_news}\n"
                    f"-------------------------\n"
                    f"🟢 <b>دخول:</b> ${current_price:.2f}\n"
                    f"🔴 <b>وقف الخسارة:</b> ${stop_loss:.2f}\n"
                    f"🎯 <b>هدف 1:</b> ${target_1:.2f}\n"
                    f"🎯 <b>هدف 2:</b> ${target_2:.2f}\n"
                )
                print(f"✅ تم إرسال {ticker}", file=sys.stderr, flush=True)
                send_telegram_alert(alert_msg)
        except Exception as e:
            pass

def run_bot():
    print("🔥 Starting Bot Thread...", file=sys.stderr, flush=True)
    send_telegram_alert("🚀 <b>تم تشغيل الماسح الجديد (بدون Finviz)!</b>\nالبوت بدأ بفحص قائمة الأسهم النشطة الآن...")
    
    while True:
        scan_stocks()
        time.sleep(300) 

@app.route('/')
def home():
    return "Scanner is Running 24/7!"

@app.route('/test')
def test_scan():
    scan_stocks()
    return "تم الفحص! شوف التليجرام واللوقز."

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.daemon = True 
    t.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
