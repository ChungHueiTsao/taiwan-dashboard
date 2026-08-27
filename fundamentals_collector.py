import json
import os
import datetime
import requests
from config import SECTORS

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/fundamentals.json'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# 官方 OpenAPI（免金鑰、非爬取互動網頁），跟先前踩雷的 MOPS 網頁版查詢表單是不同系統：
# - TWSE/TPEx 本益比/殖利率/淨值比：全上市/上櫃股票一次回傳，不用逐檔查詢
# - TWSE/TPEx 月營收：同上，含年增率欄位
# - TWSE 季度損益表(t187ap06_L_ci)：僅涵蓋「一般業」公司格式，金融/證券/保險等產業另有不同欄位格式，
#   此處故意不處理那些變體，抓不到的股票毛利率/營業利益率就留空，不讓單一產業格式差異擋掉整個 Tab
TWSE_PE_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d'
TPEX_PE_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis'
TWSE_REVENUE_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap05_L'
TPEX_REVENUE_URL = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O'
TWSE_INCOME_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci'


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
    """抓取本益比/殖利率/股價淨值比、月營收年增率、(best-effort)毛利率/營業利益率，存到 data/fundamentals.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    target_codes = _target_codes()
    stocks = {code: {} for code in target_codes}

    twse_pe = _fetch_json(TWSE_PE_URL, 'TWSE 本益比/殖利率/淨值比')
    for row in (twse_pe or []):
        code = row.get('Code', '').strip()
        if code not in stocks:
            continue
        pe = _to_float(row.get('PEratio'))
        close = _to_float(row.get('ClosePrice'))
        stocks[code].update({
            'pe': pe,
            'pb': _to_float(row.get('PBratio')),
            'dividend_yield': _to_float(row.get('DividendYield')),
            'eps': round(close / pe, 2) if (pe and close and pe > 0) else None,
        })

    tpex_pe = _fetch_json(TPEX_PE_URL, 'TPEx 本益比/殖利率/淨值比')
    for row in (tpex_pe or []):
        code = row.get('SecuritiesCompanyCode', '').strip()
        if code not in stocks:
            continue
        pe = _to_float(row.get('PriceEarningRatio'))
        dps = _to_float(row.get('DividendPerShare'))
        yld = _to_float(row.get('YieldRatio'))
        # TPEx 沒有直接給 ClosePrice，用殖利率反推：close = dps / (yld/100)
        close = (dps / (yld / 100)) if (dps and yld and yld > 0) else None
        stocks[code].update({
            'pe': pe,
            'pb': _to_float(row.get('PriceBookRatio')),
            'dividend_yield': yld,
            'eps': round(close / pe, 2) if (pe and close and pe > 0) else None,
        })

    twse_rev = _fetch_json(TWSE_REVENUE_URL, 'TWSE 月營收')
    for row in (twse_rev or []):
        code = row.get('公司代號', '').strip()
        if code not in stocks:
            continue
        stocks[code]['revenue_yoy'] = _to_float(row.get('營業收入-去年同月增減(%)'))
        stocks[code]['revenue_month'] = row.get('資料年月')

    tpex_rev = _fetch_json(TPEX_REVENUE_URL, 'TPEx 月營收')
    for row in (tpex_rev or []):
        code = row.get('公司代號', '').strip()
        if code not in stocks:
            continue
        stocks[code]['revenue_yoy'] = _to_float(row.get('營業收入-去年同月增減(%)'))
        stocks[code]['revenue_month'] = row.get('資料年月')

    twse_income = _fetch_json(TWSE_INCOME_URL, 'TWSE 季度損益表(一般業)')
    for row in (twse_income or []):
        code = row.get('公司代號', '').strip()
        if code not in stocks:
            continue
        revenue = _to_float(row.get('營業收入'))
        gross = _to_float(row.get('營業毛利（毛損）淨額'))
        operating = _to_float(row.get('營業利益（損失）'))
        if revenue and revenue != 0:
            stocks[code]['gross_margin'] = round(gross / revenue * 100, 2) if gross is not None else None
            stocks[code]['operating_margin'] = round(operating / revenue * 100, 2) if operating is not None else None

    covered = sum(1 for v in stocks.values() if v)
    if covered == 0:
        print("⚠️  完全沒有抓到任何基本面資料，保留舊的 data/fundamentals.json（如果有）")
        return None

    result = {
        "updated_at": datetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
        "stocks": stocks
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（{covered}/{len(stocks)} 檔股票有資料）")
    return result


if __name__ == '__main__':
    collect()
