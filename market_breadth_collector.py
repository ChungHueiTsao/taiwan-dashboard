import json
import os
import datetime
import requests

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/market_breadth.json'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# 全市場（上市）當日漲跌家數，跟 institutional/fundamentals 一樣走 TWSE 官方 OpenAPI（免金鑰）。
# 只算上市（TWSE，約1,378檔含ETF），不含上櫃（TPEx）——TPEx 對應端點混雜了大量非個股的
# 有價證券（測試發現單一快照就有上萬筆），要準確篩出「純上櫃個股」需要額外的證券類別欄位
# 比對，這裡先不處理，avg統計口徑只涵蓋上市部分。
TWSE_STOCK_DAY_ALL_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'


def _to_float(s):
    try:
        return float(str(s).replace(',', ''))
    except (ValueError, TypeError):
        return None


def collect():
    """抓取上市全市場當日漲跌家數，存到 data/market_breadth.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        r = requests.get(TWSE_STOCK_DAY_ALL_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        print(f"❌ 全市場漲跌家數抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None

    up = down = flat = 0
    for row in rows:
        chg = _to_float(row.get('Change'))
        if chg is None:
            continue
        if chg > 0:
            up += 1
        elif chg < 0:
            down += 1
        else:
            flat += 1

    total = up + down + flat
    if total == 0:
        print("⚠️  全市場漲跌家數：完全沒有解析到有效資料，保留舊檔（如果有）")
        return None

    result = {
        "updated_at": datetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
        "market": "TWSE上市",
        "up": up,
        "down": down,
        "flat": flat,
        "total": total,
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（上漲{up} 下跌{down} 平盤{flat}，共{total}檔）")
    return result


if __name__ == '__main__':
    collect()
