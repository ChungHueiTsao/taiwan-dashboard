import json
import os
import datetime
import requests
from config import SECTORS

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/margin_trading.json'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# 官方OpenAPI，跟fundamentals_collector同一套模式：全市場單日快照，一次拿全部再篩target_codes
TWSE_MARGIN_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN'
TPEX_MARGIN_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance'


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


def _fetch_json(url, label):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ {label} 抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None


def collect():
    """抓取上市/上櫃融資融券餘額，計算餘額增減/券資比/融資使用率，存到 data/margin_trading.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    target_codes = _target_codes()
    stocks = {}

    twse_rows = _fetch_json(TWSE_MARGIN_URL, 'TWSE 融資融券')
    for row in (twse_rows or []):
        code = row.get('股票代號', '').strip()
        if code not in target_codes:
            continue
        margin_bal = _to_float(row.get('融資今日餘額'))
        margin_prev = _to_float(row.get('融資前日餘額'))
        margin_quota = _to_float(row.get('融資限額'))
        short_bal = _to_float(row.get('融券今日餘額'))
        short_prev = _to_float(row.get('融券前日餘額'))
        stocks[code] = {
            'margin_balance': margin_bal,
            'margin_change': (margin_bal - margin_prev) if (margin_bal is not None and margin_prev is not None) else None,
            'short_balance': short_bal,
            'short_change': (short_bal - short_prev) if (short_bal is not None and short_prev is not None) else None,
            'short_margin_ratio': round(short_bal / margin_bal * 100, 2) if (short_bal is not None and margin_bal) else None,
            'margin_usage_rate': round(margin_bal / margin_quota * 100, 2) if (margin_bal is not None and margin_quota) else None,
        }

    tpex_rows = _fetch_json(TPEX_MARGIN_URL, 'TPEx 融資融券')
    for row in (tpex_rows or []):
        code = row.get('SecuritiesCompanyCode', '').strip()
        if code not in target_codes:
            continue
        margin_bal = _to_float(row.get('MarginPurchaseBalance'))
        margin_prev = _to_float(row.get('MarginPurchaseBalancePreviousDay'))
        short_bal = _to_float(row.get('ShortSaleBalance'))
        short_prev = _to_float(row.get('ShortSaleBalancePreviousDay'))
        stocks[code] = {
            'margin_balance': margin_bal,
            'margin_change': (margin_bal - margin_prev) if (margin_bal is not None and margin_prev is not None) else None,
            'short_balance': short_bal,
            'short_change': (short_bal - short_prev) if (short_bal is not None and short_prev is not None) else None,
            'short_margin_ratio': round(short_bal / margin_bal * 100, 2) if (short_bal is not None and margin_bal) else None,
            'margin_usage_rate': _to_float(row.get('MarginPurchaseUtilizationRate')),
        }

    if not stocks:
        print("⚠️  完全沒有抓到任何融資融券資料，保留舊的 data/margin_trading.json（如果有）")
        return None

    result = {
        "updated_at": datetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
        "stocks": stocks
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（{len(stocks)}/{len(target_codes)} 檔股票有資料）")
    return result


if __name__ == '__main__':
    collect()
