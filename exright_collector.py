import json
import os
import datetime
import requests
import urllib3
from config import SECTORS

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/exright_events.json'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# 官方 OpenAPI 每天只回傳「當天」的除權息事件，沒有歷史查詢端點，所以除權息還原K線
# 只能從網站上線後開始逐日累積事件，累積前的舊K線仍是原始股價，符合已與使用者確認的規劃
TWSE_EXRIGHT_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL'
TPEX_EXRIGHT_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_exright_daily'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _target_codes():
    codes = set()
    for info in SECTORS.values():
        for symbol in info['stocks']:
            codes.add(symbol.replace('.TWO', '').replace('.TW', ''))
    return codes


def _to_float(s):
    try:
        if s is None or s == '':
            return None
        return float(str(s).replace(',', ''))
    except (ValueError, TypeError):
        return None


def _roc_to_iso(roc_date):
    """民國年日期字串(如 1150910) -> ISO日期字串(2026-09-10)"""
    try:
        roc_date = roc_date.strip()
        year = int(roc_date[:3]) + 1911
        month = roc_date[3:5]
        day = roc_date[5:7]
        return f"{year}-{month}-{day}"
    except Exception:
        return None


def _fetch_json(url, label, verify):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, verify=verify)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ {label} 抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None


def _load_events():
    if not os.path.exists(OUTPUT_PATH):
        return {"stocks": {}}
    try:
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"stocks": {}}


def collect():
    """抓取當日上市/上櫃除權息事件（現金股利+股票股利），依代號+日期去重後累積存檔，
    供還原K線(除權息調整)功能逐日建立調整因子使用"""
    os.makedirs(DATA_DIR, exist_ok=True)
    target_codes = _target_codes()
    data = _load_events()
    by_code = data.setdefault("stocks", {})
    new_count = 0

    twse_rows = _fetch_json(TWSE_EXRIGHT_URL, 'TWSE 除權息事件', verify=True) or []
    for row in twse_rows:
        code = row.get('Code', '').strip()
        if code not in target_codes:
            continue
        date_iso = _roc_to_iso(row.get('Date', ''))
        if not date_iso:
            continue
        cash = _to_float(row.get('CashDividend')) or 0
        stock_ratio = _to_float(row.get('StockDividendRatio')) or 0
        events = by_code.setdefault(code, [])
        if not any(e['date'] == date_iso for e in events):
            events.append({
                "date": date_iso,
                "cash_dividend": round(cash, 4),
                "stock_dividend_ratio": round(stock_ratio, 4),
            })
            events.sort(key=lambda e: e['date'])
            new_count += 1

    tpex_rows = _fetch_json(TPEX_EXRIGHT_URL, 'TPEx 除權息事件', verify=False) or []
    for row in tpex_rows:
        code = row.get('SecuritiesCompanyCode', '').strip()
        if code not in target_codes:
            continue
        date_iso = _roc_to_iso(row.get('Date', ''))
        if not date_iso:
            continue
        cash = _to_float(row.get('CashDividend')) or 0
        stock_div = _to_float(row.get('StockDividend')) or 0
        events = by_code.setdefault(code, [])
        if not any(e['date'] == date_iso for e in events):
            events.append({
                "date": date_iso,
                "cash_dividend": round(cash, 4),
                "stock_dividend_ratio": round(stock_div, 4),
            })
            events.sort(key=lambda e: e['date'])
            new_count += 1

    data['updated_at'] = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（本次新增 {new_count} 筆除權息事件，累積 {sum(len(v) for v in by_code.values())} 筆）")
    return data


if __name__ == '__main__':
    collect()
