import json
import os
from datetime import datetime
import pytz

TAIPEI_TZ = pytz.timezone('Asia/Taipei')

def _load_institutional():
    """讀取三大法人買賣超資料（升級5），沒有檔案就回傳空字典，不影響其餘分析"""
    try:
        with open('data/institutional.json', 'r', encoding='utf-8') as f:
            return json.load(f).get('stocks', {})
    except Exception:
        return {}

def get_rating(avg_change):
    if avg_change > 2.0:
        return "🔥🔥 超強勢"
    elif avg_change > 1.0:
        return "🔥 強勢"
    elif avg_change > 0.2:
        return "⚡ 偏強"
    elif avg_change > -0.2:
        return "➡️ 持平"
    elif avg_change > -1.0:
        return "⬇️ 偏弱"
    else:
        return "💀 弱勢"

def get_market_sentiment(up_count, total):
    ratio = up_count / total if total > 0 else 0
    if ratio >= 0.6:
        return {"label": "🟢 偏多", "color": "#22c55e"}
    elif ratio >= 0.4:
        return {"label": "🟡 中性", "color": "#eab308"}
    else:
        return {"label": "🔴 偏空", "color": "#ff4444"}

def analyze():
    try:
        with open('data/latest.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ 讀取 latest.json 失敗: {e}")
        return

    inst_map = _load_institutional()

    sectors = data.get('sectors', {})
    analyzed = []
    up_count = 0

    for name, info in sectors.items():
        avg = info.get('avg_change', 0)
        rating = get_rating(avg)
        if avg > 0:
            up_count += 1

        stocks = info.get('stocks', {})
        has_inst_buy = False
        for symbol, stock in stocks.items():
            bare_code = symbol.replace('.TWO', '').replace('.TW', '')
            inst = inst_map.get(bare_code)
            if inst:
                stock.setdefault('inst_signal', inst.get('inst_signal', '中性'))
                stock.setdefault('foreign_5d', inst.get('foreign_5d', 0))
                stock.setdefault('trust_5d', inst.get('trust_5d', 0))
            if stock.get('inst_signal') == '法人同買':
                has_inst_buy = True

        score = info.get('score', 50)
        if has_inst_buy:
            score = min(100, score + 5)

        analyzed.append({
            "name": name,
            "emoji": info.get('emoji', ''),
            "avg_change": avg,
            "score": score,
            "rating": rating,
            "top_stock": info.get('top_stock', '-'),
            "top_change": info.get('top_change', 0),
            "bot_stock": info.get('bot_stock', '-'),
            "stocks": stocks
        })

    # 由強到弱排序
    analyzed.sort(key=lambda x: x['avg_change'], reverse=True)

    sentiment = get_market_sentiment(up_count, len(analyzed))
    down_count = sum(1 for s in analyzed if s['avg_change'] < -0.2)
    flat_count = len(analyzed) - up_count - down_count

    result = {
        "updated_at": data.get('updated_at', ''),
        "market_sentiment": sentiment,
        "up_count": up_count,
        "flat_count": flat_count,
        "down_count": down_count,
        "top_sector": analyzed[0]['name'] if analyzed else '-',
        "sectors": analyzed
    }

    with open('data/analysis.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 分析完成：上漲{up_count} 持平{flat_count} 下跌{down_count}")
    print(f"   市場情緒：{sentiment['label']}")
    print(f"   最強族群：{result['top_sector']}")
    return result

if __name__ == '__main__':
    analyze()
