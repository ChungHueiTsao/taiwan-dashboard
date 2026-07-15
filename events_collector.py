import json
import os
import datetime
import requests
import urllib3
from config import SECTORS

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/events.json'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}
ROC_YEAR_OFFSET = 1911

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _target_codes():
    codes = set()
    for info in SECTORS.values():
        for symbol in info['stocks']:
            codes.add(symbol.replace('.TWO', '').replace('.TW', ''))
    return codes

def _stock_name_map():
    m = {}
    for info in SECTORS.values():
        for sym in info['stocks']:
            code = sym.replace('.TWO', '').replace('.TW', '')
            m[code] = info['names'].get(sym, code)
    return m

def _roc_to_iso(roc_str):
    """把民國日期轉成 ISO 格式：'115年07月21日' 或 '1150721' -> '2026-07-21'，格式不明則回傳 None"""
    if not roc_str:
        return None
    roc_str = roc_str.strip()
    try:
        if '年' in roc_str:
            y, rest = roc_str.split('年', 1)
            m, rest = rest.split('月', 1)
            d = rest.replace('日', '').strip()
        elif len(roc_str) == 7 and roc_str.isdigit():
            y, m, d = roc_str[:3], roc_str[3:5], roc_str[5:7]
        else:
            return None
        year = int(y) + ROC_YEAR_OFFSET
        return f"{year:04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, IndexError):
        return None

def collect_ex_dividend_twse(target_codes):
    """TWSE 上市股票除權除息預告表（涵蓋個股與ETF，這裡只取我們追蹤的個股）"""
    events = []
    try:
        r = requests.get('https://www.twse.com.tw/exchangeReport/TWT48U',
                          params={'response': 'json', 'date': datetime.date.today().strftime('%Y%m%d')},
                          headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        for row in data.get('data', []):
            code = row[1].strip()
            if code not in target_codes:
                continue
            date_iso = _roc_to_iso(row[0])
            if not date_iso:
                continue
            kind = "除" + row[3] if row[3] else "除權息"
            try:
                cash = round(float(row[7]), 2) if len(row) > 7 else 0
            except (TypeError, ValueError):
                cash = 0
            events.append({"date": date_iso, "code": code, "detail": f"{kind} 現金股利{cash}元"})
    except Exception as e:
        print(f"❌ TWSE除權息資料抓取失敗，完整錯誤: {type(e).__name__}: {e}")
    return events

def collect_ex_dividend_tpex(target_codes):
    """TPEx 上櫃股票除權除息預告"""
    events = []
    try:
        r = requests.get('https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost',
                          headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        data = r.json()
        for row in data:
            code = str(row.get('SecuritiesCompanyCode', '')).strip()
            if code not in target_codes:
                continue
            date_iso = _roc_to_iso(row.get('ExRrightsExDividendDate', ''))
            if not date_iso:
                continue
            try:
                cash = round(float(row.get('CashDividend', 0)), 2)
            except (TypeError, ValueError):
                cash = 0
            kind = row.get('ExRrightsExDividend', '除權息')
            events.append({"date": date_iso, "code": code, "detail": f"{kind} 現金股利{cash}元"})
    except Exception as e:
        print(f"❌ TPEx除權息資料抓取失敗，完整錯誤: {type(e).__name__}: {e}")
    return events

def collect_investor_conferences(target_codes):
    """法說會：MOPS 對程式化查詢有機器人防護（回傳「安全性考量」拒絕頁），
    目前無法可靠自動抓取，先回傳空清單並記錄，不影響其他事件來源；
    之後若找到可行的存取方式（例如官方開放資料）可以在這裡補上"""
    try:
        return []
    except Exception as e:
        print(f"❌ 法說會資料抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return []

# 手動維護清單：總經/升降息/法說會等目前沒有可靠自動化來源的事件，先手動補充
# 之後有更好的資料源可以擴充成自動抓取。impact: 大/中/小
MANUAL_EVENTS = [
    # {"date": "2026-07-31", "type": "升降息", "title": "美國聯準會FOMC利率決議",
    #  "related_stocks": [], "impact": "大"},
]

def collect(window_days=30, lookback_days=3):
    """收集近期(含最近3天已發生)~未來30天內的事件：除權息自動抓取(TWSE+TPEx)，
    法說會/總經/升降息先用手動維護清單。任一來源失敗都不影響其他來源與已存在的資料，
    確保網頁不會因抓取失敗而崩潰"""
    os.makedirs(DATA_DIR, exist_ok=True)
    target_codes = _target_codes()
    name_map = _stock_name_map()

    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=lookback_days)
    window_end = today + datetime.timedelta(days=window_days)

    raw = []
    raw += collect_ex_dividend_twse(target_codes)
    raw += collect_ex_dividend_tpex(target_codes)

    events = []
    for e in raw:
        try:
            event_date = datetime.date.fromisoformat(e['date'])
        except (ValueError, KeyError):
            continue
        if not (window_start <= event_date <= window_end):
            continue
        code = e.get('code')
        name = name_map.get(code, code)
        events.append({
            "date": e['date'],
            "type": "除權息",
            "title": f"{name} {e.get('detail','')}".strip(),
            "related_stocks": [code] if code else [],
            "impact": "中"
        })

    for e in MANUAL_EVENTS:
        try:
            event_date = datetime.date.fromisoformat(e['date'])
        except (ValueError, KeyError):
            continue
        if window_start <= event_date <= window_end:
            events.append(e)

    for e in collect_investor_conferences(target_codes):
        events.append(e)

    events.sort(key=lambda x: x['date'])

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（{len(events)} 筆事件）")
    return events

if __name__ == '__main__':
    collect()
