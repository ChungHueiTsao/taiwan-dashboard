from flask import Flask, jsonify, render_template, redirect, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import os
import sys
import json
import requests
import logging
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

TAIPEI_TZ = pytz.timezone('Asia/Taipei')

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
    """/api/refresh 用：只用盤中分時資料更新現價，不重抓整年K線（比 run_full_update 快很多）"""
    logging.info("⏱️  開始盤中即時更新...")
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

# 啟動時若無資料立刻執行一次
if not os.path.exists('data/latest.json'):
    logging.info("📦 初次啟動，立刻抓取資料...")
    run_full_update()

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
    kline = load_cached_kline(symbol)
    if not kline:
        kline = get_kline_history(symbol)
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
