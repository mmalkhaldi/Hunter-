from flask import Flask
import threading
import requests
import finnhub
from finvizfinance.screener.overview import Overview
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

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}", file=sys.stderr, flush=True)

def scan_stocks():
    print(f"\n⏳ [{datetime.now().strftime('%H:%M:%S')}] جاري مسح السوق بالكامل عبر Finviz...", file=sys.stderr, flush=True)
    
    try:
        # إعداد الفلاتر (نفس شروطك)
        screener = Overview()
        filters_dict = {
            'Price': 'Under $15',
            'Average Volume': 'Over 500K',
            'Float': 'Under 50M',
            'Relative Volume': 'Over 2',
            'RSI (14)': '50 to 65',
            '20-Day Simple Moving Average': 'Price above SMA20'
        }
        screener.set_filter(filters_dict=filters_dict)
        
        # سحب النتائج
        df = screener.screener_view()
        
        if df is None or df.empty:
            print("⚠️ لا توجد أسهم تطابق الشروط حالياً.", file=sys.stderr, flush=True)
            return

        tickers = df['Ticker'].tolist()
        print(f"🎯 تم العثور على {len(tickers)} سهم: {', '.join(tickers)}", file=sys.stderr, flush=True)
        
        for ticker in tickers:
            try:
                # جلب السعر اللحظي والخبر من Finnhub
                quote = finnhub_client.quote(ticker)
                current_price = quote.get('c') 
                prev_close = quote.get('pc')  
                day_low = quote.get('l')      
                
                if not current_price or current_price == 0: continue
                    
                change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
                
                stop_loss = max(current_price * 0.96, day_low * 0.99) 
                target_1 = current_price * 1.05
                target_2 = current_price * 1.10
                
                news = finnhub_client.company_news(ticker, _from=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), to=datetime.now().strftime('%Y-%m-%d'))
                latest_news = news[0]['headline'] if news else "لا توجد أخبار حديثة"
                
                alert_msg = (
                    f"🎯 <b>فرصة زخم: {ticker}</b> 🎯\n\n"
                    f"💵 <b>السعر:</b> ${current_price:.2f} ({change_pct:.1f}%)\n"
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
                print(f"Error processing {ticker}: {e}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Error in screener: {e}", file=sys.stderr, flush=True)

def run_bot():
    print("🔥 Starting Dynamic Scanner...", file=sys.stderr, flush=True)
    send_telegram_alert("🚀 <b>تم تشغيل الماسح الديناميكي!</b>\nالبوت بدأ بمسح السوق بحثاً عن الزخم...")
    
    while True:
        scan_stocks()
        time.sleep(300) 

@app.route('/')
def home():
    return "Dynamic Scanner is Running 24/7!"

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
