import csv
import io
import json
import os
import datetime
import requests
import urllib3
from config import SECTORS

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/big_holders.json'
HISTORY_PATH = f'{DATA_DIR}/big_holders_history.json'  # 存最近一次成功抓到的快照，供下週比對變化

TDCC_URL = 'https://opendata.tdcc.com.tw/getOD.ashx?id=1-5'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# TDCC集保庫存持股分級：12=400-600張、13=600-800張、14=800-1000張、15=1000張以上
# 400張以上（含1000張以上）大戶 = 級距12~15加總
BIG_HOLDER_TIERS = {'12', '13', '14', '15'}

# TDCC 憑證同樣缺少 Subject Key Identifier 擴充欄位，Python 3.13 OpenSSL 3.x 會嚴格拒絕
# （瀏覽器/curl 不受影響），停用憑證驗證：抓的是公開股權分散表，非帳密等敏感操作
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _target_codes():
    codes = set()
    for info in SECTORS.values():
        for symbol in info['stocks']:
            codes.add(symbol.replace('.TWO', '').replace('.TW', ''))
    return codes

def _load_snapshot(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def collect():
    """抓取集保結算所股權分散表，計算400張以上大戶持股比，與上週快照比較變化。
    TDCC 每週更新一次，本函數設計為每週五排程執行一次"""
    os.makedirs(DATA_DIR, exist_ok=True)
    target_codes = _target_codes()

    try:
        r = requests.get(TDCC_URL, headers=HEADERS, timeout=30, verify=False)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"❌ 大戶動向資料抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None

    try:
        reader = csv.reader(io.StringIO(text))
        next(reader)  # 跳過標題列
        data_date = None
        holder_ratio = {}
        for row in reader:
            if len(row) < 6:
                continue
            date_str, code, tier, holders, shares, ratio = row[:6]
            code = code.strip()
            if code not in target_codes:
                continue
            data_date = data_date or date_str
            if tier in BIG_HOLDER_TIERS:
                try:
                    holder_ratio[code] = holder_ratio.get(code, 0) + float(ratio)
                except ValueError:
                    pass
    except Exception as e:
        print(f"❌ 大戶動向資料解析失敗，完整錯誤: {type(e).__name__}: {e}")
        return None

    if not holder_ratio:
        print("⚠️  大戶動向：本週查無符合追蹤股票的資料")
        return None

    prev_history = _load_snapshot(HISTORY_PATH)
    prev_stocks = (prev_history or {}).get('stocks', {})
    prev_date = (prev_history or {}).get('data_date')

    stocks = {}
    for code, ratio in holder_ratio.items():
        ratio = round(ratio, 2)
        prev_ratio = prev_stocks.get(code, {}).get('holder_ratio')
        ratio_change = round(ratio - prev_ratio, 2) if prev_ratio is not None else None
        stocks[code] = {"holder_ratio": ratio, "ratio_change": ratio_change}

    result = {
        "updated_at": datetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
        "data_date": data_date,
        "stocks": stocks
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（{len(stocks)} 檔股票，資料日期 {data_date}）")

    # 只有拿到「真正新一週」的資料才更新比對基準，避免同一週重複執行時
    # 把這次的資料拿去跟自己比較，導致下週的 ratio_change 失真
    if data_date != prev_date:
        with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ 已更新比對基準快照（{data_date}）")
    else:
        print(f"ℹ️  資料日期與上次相同（{data_date}），不更新比對基準")

    return result

if __name__ == '__main__':
    collect()
