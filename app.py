from flask import Flask
import threading
import requests
from bs4 import BeautifulSoup
import finnhub
from datetime import datetime, timedelta
import time
import os
import sys

app = Flask(__name__)

# ==========================================
# 1. الإعدادات الأساسية (تقرأ من Render بأمان)
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "9148905124:AAGIuJ7ZbI4LSaVVtFpnboVwXXB3zNd2CNg")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "5490419100")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "dbguue9r01qjpoc3bgogdbguue9r01qjpoc3bgp0")

FINVIZ_URL = "https://elite.finviz.com/screener/stocks?f=sh_price_u15%2Csh_avgvol_o500%2Csh_float_u50%2Csh_relvol_o2%2Ccap_small%2Cta_rsi_50to65%2Cta_sma20_pa"

COOKIE_STRING = "chartsTheme=dark; finviz_ab=registerElitePromo%3A0%3B0%3B1775299530; survey_dialog_cohort=0; finviz_t=f7328276-944f-4a19-ae54-2778ef0dc0dd; __qca=P1-ffb969d4-a870-4358-8cea-dc4ecf9fabf6; _ga=GA1.1.1943187939.1775299561; __cc_id=b52a83dd4d346e719b38a9bad3d7a581; insiderTradingUrl=tc%3D7; cto_bidid=MN3lG190TnVBTW8lMKZjWHoaGU3TFNHD0hZCuyR1dTZQUXMGtlWHDViuyRhVbhSaVvPMzhyT2pvUW52VUQ1dkxKJTJCJTGbnI2aXh6TSuyQMzZcllC2padnNFEUlMkYxeVdvOTBsNXHQcng4ZGN0aHL3OvG2T0jBJTNTR; .AspNetCore.Session=CfDJ8K%2BNWRTf4lNlgLm2TjEMMTS1IaRSVbDzwgdNnZqn%2BoCM2CEVIkx%2BnaNoz89jm1H1AVjG1%2BEPOP3YweSXOCQLDve9v56g%2BE37bZ%2FF9%2B2Bdna23F8Saxr3DHr4xDjy8Z52t08Duth6RLrjr3%2FrJH%2FoAk8A31m%2BJaWxocKwrf6pPnDceUBn; .ASPXAUTH=48BC2194BD546BB39F5A3FCC9B575C05884D6CD8186AF3A954E99602AC22934084F84BD0F3101F008AA6DF5F8CB15CC4B873231CB4264381CB1172E5CB38C1425A0D35FFCDB6644755B633DE2D7D9454FC206362DAFF8A25713C0ED0E010E98180E844720FEF7FF569421C74735FE195A6C361AF81EEA8707F25EE0E5FD7453458D0D01C52C7746C4F2CC8B90459F1BB60B17ADA7DADB96997E4D7F63C39816275278BBF1EDB86DA04A9812220B573AA143FABF8AD063731AB83BC6ED7E1ACE2B2197C737644203FCB4E33AE494435E6D1C807; ic_tag_manager=UAT; screenerBackUrl=/screener/stocks; screenerBackUrlStocks=/screener/stocks; _ga_9T4RBK8XLD=GS2.1.s1793229336$o7$g1$t1793229339$j57$l0$h0; _ga_ZT9VQEWD4N=GS2.1.s1793229331$o8$g1$t1793229339$j52$l0$h0; _awl=2.1793229339.5-04734e2ca099941e45dbb340aa463f83-6763652d6575726f70652d7765737431-0"

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}", file=sys.stderr, flush=True)

def get_finviz_tickers():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Cookie': COOKIE_STRING
    }
    try:
        response = requests.get(FINVIZ_URL, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        tickers = [a_tag.text.strip() for a_tag in soup.find_all('a', class_='screener-link-primary')]
        return tickers
    except Exception as e:
        print(f"Error fetching Finviz: {e}", file=sys.stderr, flush=True)
        return []

def scan_and_alert():
    print(f"\n⏳ [{datetime.now().strftime('%H:%M:%S')}] جاري فحص Finviz...", file=sys.stderr, flush=True)
    tickers = get_finviz_tickers()
    
    if not tickers:
        print("⚠️ لا توجد أسهم في الفلتر حالياً.", file=sys.stderr, flush=True)
        return

    print(f"🎯 تم العثور على {len(tickers)} سهم. جاري جلب الأسعار...", file=sys.stderr, flush=True)
    
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
            )
            print(f"✅ تم إرسال {ticker}", file=sys.stderr, flush=True)
            send_telegram_alert(alert_msg)
        except Exception as e:
            print(f"Error processing {ticker}: {e}", file=sys.stderr, flush=True)

def run_bot():
    print("🔥 Starting Bot Thread...", file=sys.stderr, flush=True)
    send_telegram_alert("🚀 <b>تم تشغيل السيرفر بنجاح (بالمفتاح الجديد)!</b>\nالبوت بدأ بفحص الأسهم الآن...")
    
    while True:
        scan_and_alert()
        time.sleep(300) 

@app.route('/')
def home():
    return "Beast Scanner is Running 24/7!"

@app.route('/test')
def test_scan():
    scan_and_alert()
    return "تم الفحص! شوف التليجرام واللوقز."

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.daemon = True 
    t.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
