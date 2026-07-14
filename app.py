from flask import Flask, jsonify, render_template, redirect, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import os
import sys
import json
import requests
import logging
import threading
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# ^ 在 URL 路徑裡容易被中介層/瀏覽器編碼成 %5E 造成路由或快取檔名問題，
# 對外一律用不含特殊字元的別名，內部再轉換成 yfinance 真正的代號
SYMBOL_MAP = {
    "TWII": "^TWII",      # 加權指數
    "TWOII": "^TWOII",    # 櫃買指數
    "TAIFEX": "^TWII",    # 台指期（無可靠免費歷史資料來源，暫用加權指數代替）
}

def resolve_symbol(symbol):
    """把對外別名（TWII/TWOII/TAIFEX）轉成 yfinance 實際代號，一般股票代號原樣返回"""
    return SYMBOL_MAP.get(symbol, symbol)

def is_market_hours():
    now = datetime.now(TAIPEI_TZ)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return t >= datetime.strptime('09:00', '%H:%M').time() and t <= datetime.strptime('13:30', '%H:%M').time()

def run_full_update():
    logging.info("🚀 開始完整更新...")
    try:
        from institutional_collector import collect as collect_institutional
        from data_collector import collect_all
        from analyzer import analyze
        from dashboard_generator import generate
        collect_institutional()
        collect_all()
        analyze()
        generate()
        logging.info("✅ 更新完成")
    except Exception as e:
        logging.error(f"❌ 更新失敗: {e}")

def refresh_now():
    """/api/refresh 用：盤中時段只更新現價（快），非盤中時段跑完整更新（含重抓K線）"""
    if is_market_hours():
        logging.info("⏱️  盤中時段，開始盤中即時更新...")
        try:
            from data_collector import refresh_intraday_prices
            from analyzer import analyze
            from dashboard_generator import generate
            refresh_intraday_prices()
            analyze()
            generate()
            logging.info("✅ 盤中更新完成")
        except Exception as e:
            logging.error(f"❌ 盤中更新失敗: {e}")
    else:
        logging.info("🌙 非盤中時段，改跑完整更新...")
        run_full_update()

def keep_alive():
    try:
        url = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:8080')
        requests.get(f"{url}/health", timeout=5)
        logging.debug("💓 Keep-alive ping sent")
    except:
        pass

# 排程設定
scheduler = BackgroundScheduler(timezone=TAIPEI_TZ)
scheduler.add_job(
    run_full_update,
    CronTrigger(day_of_week='mon-fri', hour=8, minute=50, timezone=TAIPEI_TZ),
    id='daily_update',
    name='每日8:50更新'
)
scheduler.add_job(keep_alive, 'interval', minutes=14, id='keep_alive')
scheduler.start()

# 啟動時若無資料，在背景執行完整更新，不阻擋網站上線（Render 免費方案磁碟不持久，
# 每次重新部署都要重新抓一次，若同步等待會讓部署卡在健康檢查上好幾分鐘）
if not os.path.exists('data/latest.json'):
    logging.info("📦 初次啟動，背景抓取資料中...")
    threading.Thread(target=run_full_update, daemon=True).start()

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except:
        return "<h1>儀表板載入中，請稍後重新整理...</h1>", 503

@app.route('/api/data')
def api_data():
    try:
        with open('data/analysis.json', 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"error": "資料尚未準備好"}), 503

@app.route('/api/refresh')
def api_refresh():
    redirect_after = 'redirect' in request.args if hasattr(request, 'args') else False
    refresh_now()
    if redirect_after:
        return redirect('/')
    return jsonify({"status": "ok", "message": "更新完成", "time": datetime.now(TAIPEI_TZ).strftime('%Y/%m/%d %H:%M')})

@app.route('/api/kline/<symbol>')
def api_kline(symbol):
    from data_collector import load_cached_kline, get_kline_history
    real_symbol = resolve_symbol(symbol)
    kline = load_cached_kline(symbol if symbol in SYMBOL_MAP else real_symbol)
    if not kline:
        kline = get_kline_history(real_symbol, cache_name=symbol if symbol in SYMBOL_MAP else None)
    if not kline:
        return jsonify({"error": f"{symbol} 無法取得K線資料"}), 404
    return jsonify(kline)

@app.route('/health')
def health():
    last = "無資料"
    try:
        with open('data/analysis.json', 'r', encoding='utf-8') as f:
            d = json.load(f)
            last = d.get('updated_at', '未知')
    except:
        pass
    return jsonify({"status": "ok", "last_update": last})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
