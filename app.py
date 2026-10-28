from flask import Flask
import threading
import requests
from bs4 import BeautifulSoup
import finnhub
from datetime import datetime, timedelta
import time
import os

app = Flask(__name__)

# ==========================================
# 1. الإعدادات الأساسية (تم تحديث المفتاح)
# ==========================================
TELEGRAM_TOKEN = "9148905124:AAGt8y6NoMdzGRfsnQIwVEq5kI0neVLA3t0"
TELEGRAM_CHAT_ID = "5490419100"
FINNHUB_API_KEY = "dbguue9r01qjpoc3bgog" # المفتاح الجديد الصحيح

FINVIZ_URL = "https://elite.finviz.com/screener/stocks?ft=3&f=sh_price_u10%2Csh_avgvol_o1000%2Ccap_small%2Cta_rsi_50to65%2Cta_sma20_pa%2Csh_relvol_o3"

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}", flush=True)

def get_finviz_tickers():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(FINVIZ_URL, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        tickers = [a_tag.text.strip() for a_tag in soup.find_all('a', class_='screener-link-primary')]
        return tickers
    except:
        return []

def scan_and_alert():
    # flush=True عشان السجل يظهر في Render غصباً
    print(f"\n⏳ [{datetime.now().strftime('%H:%M:%S')}] جاري فحص Finviz...", flush=True)
    tickers = get_finviz_tickers()
    
    if not tickers:
        print("⚠️ لا توجد أسهم في الفلتر حالياً.", flush=True)
        return

    print(f"🎯 تم العثور على {len(tickers)} سهم. جاري جلب الأسعار...", flush=True)
    
    for ticker in tickers:
        try:
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
                f"🎯 <b>فرصة: {ticker}</b> 🎯\n\n"
                f"💵 <b>السعر:</b> ${current_price:.2f} ({change_pct:.1f}%)\n"
                f"📰 <b>الخبر:</b> {latest_news}\n"
                f"-------------------------\n"
                f"🟢 <b>دخول:</b> ${current_price:.2f}\n"
                f"🔴 <b>وقف الخسارة:</b> ${stop_loss:.2f}\n"
                f"🎯 <b>هدف 1:</b> ${target_1:.2f}\n"
                f"🎯 <b>هدف 2:</b> ${target_2:.2f}\n"
                f"⚠️ <i>تأكد من السيولة والشارت قبل الدخول.</i>"
            )
            print(f"✅ تم إرسال {ticker}", flush=True)
            send_telegram_alert(alert_msg)
        except Exception as e:
            print(f"Error processing {ticker}: {e}", flush=True)

def run_bot():
    # نرسل رسالة تأكيد أول ما يشتغل البوت
    send_telegram_alert("🚀 <b>تم تشغيل السيرفر بنجاح!</b>\nالبوت بدأ بفحص الأسهم الآن...")
    
    while True:
        scan_and_alert()
        time.sleep(300) 

@app.route('/')
def home():
    return "Beast Scanner is Running 24/7!"

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
