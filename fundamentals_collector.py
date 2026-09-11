import json
import os
import datetime
import requests
import urllib3
from config import SECTORS

# TPEx 憑證缺少 Subject Key Identifier 擴充欄位，Python 3.13 OpenSSL 3.x 會嚴格拒絕
# （瀏覽器/curl 不受影響），停用憑證驗證：抓的是公開財務資料，非帳密等敏感操作
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/fundamentals.json'
PE_HISTORY_PATH = f'{DATA_DIR}/pe_history.json'  # 本益比河流圖用：逐日累積，官方API不提供歷史，從現在開始累積
PE_HISTORY_MAX_DAYS = 250
DIVIDEND_HISTORY_PATH = f'{DATA_DIR}/dividend_history.json'  # 股利政策：依股利年度累積，年度資料到齊後才會出現
FIN_RATIO_HISTORY_PATH = f'{DATA_DIR}/fin_ratio_history.json'  # 多年度財務比率趨勢：依營收月份(季度)累積
FIN_RATIO_HISTORY_MAX = 20  # 最多保留20季（約5年，但官方API僅提供當期，同樣從現在開始累積）

TWSE_DIVIDEND_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap45_L'
TPEX_DIVIDEND_URL = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap39_O'

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
        r = requests.get(url, headers=HEADERS, timeout=30, verify=('tpex.org.tw' not in url))
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ {label} 抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _update_pe_history(stocks, target_codes):
    """逐日累積本益比，供本益比河流圖(PE Band)使用。官方API只給當日快照，
    所以歷史深度會隨網站上線時間自然累積，不做回補"""
    history = _load_json(PE_HISTORY_PATH) or {"series": {}}
    series = history.setdefault("series", {})
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    for code in target_codes:
        pe = stocks.get(code, {}).get('pe')
        if pe is None:
            continue
        points = series.setdefault(code, [])
        if points and points[-1].get('date') == today:
            points[-1]['pe'] = pe
        else:
            points.append({"date": today, "pe": pe})
        series[code] = points[-PE_HISTORY_MAX_DAYS:]
    with open(PE_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _update_dividend_history(target_codes):
    """累積股利政策(歷年配息)，依「股利年度」去重，同一年度重複抓取只會覆蓋更新，
    不會產生重複紀錄。TWSE(t187ap45_L)/TPEx(mopsfin_t187ap39_O)兩份官方資料集
    欄位命名不同，各自對應抓取"""
    history = _load_json(DIVIDEND_HISTORY_PATH) or {"stocks": {}}
    by_code = history.setdefault("stocks", {})

    twse_rows = _fetch_json(TWSE_DIVIDEND_URL, 'TWSE 股利分派情形') or []
    for row in twse_rows:
        code = row.get('公司代號', '').strip()
        if code not in target_codes:
            continue
        year = row.get('股利年度', '').strip()
        if not year:
            continue
        cash = sum(_to_float(row.get(k)) or 0 for k in [
            '股東配發-盈餘分配之現金股利(元/股)',
            '股東配發-法定盈餘公積發放之現金(元/股)',
            '股東配發-資本公積發放之現金(元/股)',
        ])
        stock_div = sum(_to_float(row.get(k)) or 0 for k in [
            '股東配發-盈餘轉增資配股(元/股)',
            '股東配發-法定盈餘公積轉增資配股(元/股)',
            '股東配發-資本公積轉增資配股(元/股)',
        ])
        years = by_code.setdefault(code, {})
        years[year] = {
            "year": year,
            "cash_dividend": round(cash, 4),
            "stock_dividend": round(stock_div, 4),
            "progress": row.get('決議（擬議）進度', ''),
            "meeting_date": row.get('股東會日期', ''),
        }

    tpex_rows = _fetch_json(TPEX_DIVIDEND_URL, 'TPEx 股利分派情形') or []
    for row in tpex_rows:
        code = row.get('公司代號', '').strip()
        if code not in target_codes:
            continue
        year = row.get('股利年度', '').strip()
        if not year:
            continue
        cash = sum(_to_float(row.get(k)) or 0 for k in [
            '股東配發內容-盈餘分配之現金股利(元/股)',
            '股東配發內容-法定盈餘公積、資本公積發放之現金(元/股)',
        ])
        stock_div = sum(_to_float(row.get(k)) or 0 for k in [
            '股東配發內容-盈餘轉增資配股(元/股)',
            '股東配發內容-法定盈餘公積、資本公積轉增資配股(元/股)',
        ])
        years = by_code.setdefault(code, {})
        # TPEx 資料集是歷史累積(較舊年度)，若該年度已有TWSE較新資料則不覆蓋
        if year not in years:
            years[year] = {
                "year": year,
                "cash_dividend": round(cash, 4),
                "stock_dividend": round(stock_div, 4),
                "progress": "",
                "meeting_date": row.get('股東會日期配盈餘/待彌補虧損(元)', ''),
            }

    with open(DIVIDEND_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    covered = sum(1 for v in by_code.values() if v)
    print(f"✅ 已更新 {DIVIDEND_HISTORY_PATH}（{covered} 檔股票有股利紀錄）")


def _update_fin_ratio_history(stocks, target_codes):
    """累積季度財務比率(毛利率/營業利益率/營收年增率)，依「資料年月」去重，
    供多年度財務比率趨勢圖使用。官方API僅提供當期，深度隨時間自然累積"""
    history = _load_json(FIN_RATIO_HISTORY_PATH) or {"series": {}}
    series = history.setdefault("series", {})
    for code in target_codes:
        s = stocks.get(code, {})
        period = s.get('revenue_month')
        if not period:
            continue
        points = series.setdefault(code, [])
        entry = {
            "period": period,
            "revenue_yoy": s.get('revenue_yoy'),
            "gross_margin": s.get('gross_margin'),
            "operating_margin": s.get('operating_margin'),
        }
        if points and points[-1].get('period') == period:
            points[-1] = entry
        else:
            points.append(entry)
        series[code] = points[-FIN_RATIO_HISTORY_MAX:]
    with open(FIN_RATIO_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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

    _update_pe_history(stocks, target_codes)
    _update_fin_ratio_history(stocks, target_codes)
    _update_dividend_history(target_codes)

    return result


if __name__ == '__main__':
    collect()
