import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime
import pytz
from config import SECTORS

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
DATA_DIR = 'data'

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

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
    hist_path = f'{DATA_DIR}/history.csv'
    df_new = pd.DataFrame(history_rows)
    if os.path.exists(hist_path):
        df_old = pd.read_csv(hist_path)
        df_old = df_old[df_old['date'] != now.strftime('%Y-%m-%d')]
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_combined = df_new
    df_combined.tail(20 * len(SECTORS)).to_csv(hist_path, index=False)
    print(f"✅ 已更新 data/history.csv")

    return result

if __name__ == '__main__':
    collect_all()
