import yfinance as yf
import pandas as pd
import json
import os
import base64
import requests
from datetime import datetime
import pytz
from config import SECTORS

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
DATA_DIR = 'data'
HIST_PATH = f'{DATA_DIR}/history.csv'

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def _github_config():
    """讀取用來持久化 history.csv 的 GitHub 設定（未設定則停用此功能）"""
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not token or not repo:
        return None
    return {
        "token": token,
        "repo": repo,
        "branch": os.environ.get('GITHUB_BRANCH', 'master'),
        "url": f"https://api.github.com/repos/{repo}/contents/data/history.csv"
    }

def restore_history_from_github():
    """開機時若本機沒有 history.csv（免費方案磁碟不持久），從 GitHub repo 還原"""
    if os.path.exists(HIST_PATH):
        return
    cfg = _github_config()
    if not cfg:
        return
    try:
        r = requests.get(cfg['url'], headers={"Authorization": f"token {cfg['token']}"},
                          params={"ref": cfg['branch']}, timeout=10)
        if r.status_code == 200:
            ensure_dirs()
            with open(HIST_PATH, 'wb') as f:
                f.write(base64.b64decode(r.json()['content']))
            print("✅ 已從 GitHub 還原歷史資料 data/history.csv")
    except Exception as e:
        print(f"⚠️  從 GitHub 還原歷史資料失敗: {e}")

def push_history_to_github():
    """把最新的 history.csv 推回 GitHub repo，避免免費方案重啟後資料遺失"""
    cfg = _github_config()
    if not cfg or not os.path.exists(HIST_PATH):
        return
    headers = {"Authorization": f"token {cfg['token']}"}
    try:
        with open(HIST_PATH, 'rb') as f:
            content_b64 = base64.b64encode(f.read()).decode()
        sha = None
        r = requests.get(cfg['url'], headers=headers, params={"ref": cfg['branch']}, timeout=10)
        if r.status_code == 200:
            sha = r.json().get('sha')
        payload = {
            "message": f"chore: 更新歷史資料 {datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}",
            "content": content_b64,
            "branch": cfg['branch']
        }
        if sha:
            payload["sha"] = sha
        put_r = requests.put(cfg['url'], headers=headers, json=payload, timeout=15)
        if put_r.status_code in (200, 201):
            print("✅ 已將歷史資料同步回 GitHub")
        else:
            print(f"⚠️  同步歷史資料到 GitHub 失敗: {put_r.status_code} {put_r.text[:200]}")
    except Exception as e:
        print(f"⚠️  同步歷史資料到 GitHub 發生錯誤: {e}")

def get_stock_data(symbol):
    """抓取單一股票資料與近一年K線"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1y')
        if hist.empty:
            return None
        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest
        price = round(float(latest['Close']), 2)
        prev_price = round(float(prev['Close']), 2)
        change_pct = round((price - prev_price) / prev_price * 100, 2) if prev_price > 0 else 0
        volume = int(latest['Volume'])
        avg_volume = int(hist['Volume'].tail(5).mean()) if len(hist) >= 5 else volume
        volume_ratio = round(volume / avg_volume, 2) if avg_volume > 0 else 1.0

        opens = [round(float(x), 2) for x in hist['Open']]
        closes = [round(float(x), 2) for x in hist['Close']]
        return {
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "volume_ratio": volume_ratio,
            "kline": {
                "dates": hist.index.strftime('%Y-%m-%d').tolist(),
                "o": opens,
                "h": [round(float(x), 2) for x in hist['High']],
                "l": [round(float(x), 2) for x in hist['Low']],
                "c": closes,
                "v": [int(x) for x in hist['Volume']],
                "colors": ["#ff4444" if c >= o else "#22c55e" for o, c in zip(opens, closes)]
            }
        }
    except Exception as e:
        print(f"  ⚠️  {symbol} 抓取失敗: {e}")
        return None

def collect_all():
    """抓取所有族群股票資料"""
    ensure_dirs()
    restore_history_from_github()
    now = datetime.now(TAIPEI_TZ)
    print(f"\n🚀 開始抓取資料 {now.strftime('%Y/%m/%d %H:%M')}")

    result = {
        "updated_at": now.strftime('%Y/%m/%d %H:%M'),
        "sectors": {}
    }

    history_rows = []

    for sector_name, sector_info in SECTORS.items():
        print(f"\n📊 {sector_info['emoji']} {sector_name}")
        stocks_data = {}
        changes = []

        for symbol in sector_info['stocks']:
            name = sector_info['names'].get(symbol, symbol)
            data = get_stock_data(symbol)
            if data:
                stocks_data[symbol] = {
                    "name": name,
                    **data
                }
                changes.append(data['change_pct'])
                status = "🔴" if data['change_pct'] > 0 else "🟢"
                print(f"  {status} {name}: {data['price']} ({data['change_pct']:+.2f}%)")
            else:
                stocks_data[symbol] = {
                    "name": name,
                    "price": 0,
                    "change_pct": 0,
                    "volume": 0,
                    "volume_ratio": 1.0
                }

        avg_change = round(sum(changes) / len(changes), 2) if changes else 0
        score = min(100, max(0, int(50 + avg_change * 10)))

        sorted_stocks = sorted(
            [(s, d) for s, d in stocks_data.items() if d['price'] > 0],
            key=lambda x: x[1]['change_pct'],
            reverse=True
        )
        top_stock = sorted_stocks[0][1]['name'] if sorted_stocks else "-"
        top_change = sorted_stocks[0][1]['change_pct'] if sorted_stocks else 0
        bot_stock = sorted_stocks[-1][1]['name'] if sorted_stocks else "-"

        result['sectors'][sector_name] = {
            "emoji": sector_info['emoji'],
            "avg_change": avg_change,
            "score": score,
            "top_stock": top_stock,
            "top_change": top_change,
            "bot_stock": bot_stock,
            "stocks": stocks_data
        }

        history_rows.append({
            "date": now.strftime('%Y-%m-%d'),
            "sector": sector_name,
            "avg_change": avg_change,
            "score": score
        })

    # 儲存 latest.json
    with open(f'{DATA_DIR}/latest.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已儲存 data/latest.json")

    # 追加 history.csv
    df_new = pd.DataFrame(history_rows)
    if os.path.exists(HIST_PATH):
        df_old = pd.read_csv(HIST_PATH)
        df_old = df_old[df_old['date'] != now.strftime('%Y-%m-%d')]
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_combined = df_new
    df_combined.tail(60 * len(SECTORS)).to_csv(HIST_PATH, index=False)
    print(f"✅ 已更新 data/history.csv")

    push_history_to_github()

    return result

if __name__ == '__main__':
    collect_all()
