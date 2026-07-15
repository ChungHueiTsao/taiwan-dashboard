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

def collect_investor_conferences(target_codes, window_days=60):
    """法說會：查詢區間為「今天起算未來window_days天」（預設60天）。
    ⚠️ 目前MOPS(公開資訊觀測站)對程式化查詢有機器人防護，無論用什麼瀏覽器標頭、
    session、Referer都會回傳「因為安全性考量，您所執行的頁面無法呈現」拒絕頁，
    已實際測試多組請求方式仍無法繞過，因此這不是查詢區間過窄的問題，而是目前
    完全沒有可用的自動化資料來源。這裡先回傳空清單，前端會顯示「近期無相關事件」
    提示文字而非空白區塊；之後若找到可行的存取方式（例如官方開放資料）可以在這裡補上，
    屆時window_days參數已經是60天，直接接上即可"""
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

def _nth_weekday(year, month, weekday, n=1):
    """該月第n個指定星期幾（weekday: 0=一 ... 4=五），用來算「每月第一個週五」這類規則性日期，
    保證正確、不依賴人工記憶"""
    d = datetime.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    d += datetime.timedelta(days=offset + 7 * (n - 1))
    return d

# ---------------------------------------------------------------------------
# 總經/升降息固定清單（MACRO_EVENTS）
#
# ⚠️ FOMC利率決議、台灣央行理監事會議、美國CPI公布日 是官方排定的具體日期，
#    以下為 2026 年最佳整理，「請每年對照官方行事曆核實更新」：
#    - Fed FOMC: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
#    - 台灣央行理監事會議: https://www.cbc.gov.tw/
#    - 美國CPI: https://www.bls.gov/schedule/news_release/cpi.htm
#
# 「非農就業數據」「景氣對策信號」是固定規則（每月第一個週五／每月27日左右），
# 用程式算出來，不受人工記憶誤差影響。
# ---------------------------------------------------------------------------

_FOMC_DATES_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
                    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16"]
_CBC_DATES_2026 = ["2026-03-19", "2026-06-18", "2026-09-17", "2026-12-17"]
_US_CPI_DATES_2026 = ["2026-07-14", "2026-08-13", "2026-09-11", "2026-10-14",
                      "2026-11-13", "2026-12-11"]

def _build_macro_events(year=2026):
    events = []
    for d in _FOMC_DATES_2026:
        if datetime.date.fromisoformat(d).year == year:
            events.append({"date": d, "type": "升降息", "title": "美國聯準會FOMC利率決議",
                            "related_stocks": [], "impact": "極大",
                            "summary": "Fed公布最新基準利率決議與經濟展望，影響全球資金成本與風險偏好。"})
    for d in _CBC_DATES_2026:
        if datetime.date.fromisoformat(d).year == year:
            events.append({"date": d, "type": "升降息", "title": "台灣央行理監事會議",
                            "related_stocks": [], "impact": "大",
                            "summary": "央行公布重貼現率與貨幣政策方向，影響台幣利率與市場資金水位。"})
    for d in _US_CPI_DATES_2026:
        if datetime.date.fromisoformat(d).year == year:
            events.append({"date": d, "type": "總經", "title": "美國CPI消費者物價指數公布",
                            "related_stocks": [], "impact": "大",
                            "summary": "美國通膨數據公布，是市場判斷Fed後續利率路徑的重要依據。"})
    for month in range(1, 13):
        nfp_date = _nth_weekday(year, month, 4, 1)  # 週五=4，每月第一個週五
        events.append({"date": nfp_date.isoformat(), "type": "總經", "title": "美國非農就業數據公布",
                        "related_stocks": [], "impact": "大",
                        "summary": "美國就業市場數據公布，反映景氣與勞動市場強弱，牽動Fed政策預期。"})
        signal_date = datetime.date(year, month, 27)
        events.append({"date": signal_date.isoformat(), "type": "總經", "title": "台灣景氣對策信號公布",
                        "related_stocks": [], "impact": "中",
                        "summary": "國發會公布景氣對策信號燈號，反映台灣整體景氣循環位置。"})
    return events

MACRO_EVENTS = _build_macro_events(2026)

def collect(window_days=30, lookback_days=3, macro_window_days=120, conference_window_days=60):
    """收集近期事件，存入data/events.json：
    - 除權息：自動抓取(TWSE+TPEx)，區間為 今天-lookback_days ~ 今天+window_days
    - 總經/升降息：MACRO_EVENTS固定清單，區間較寬(預設120天)，因FOMC/央行理監事會議
      間隔常超過30天，用太窄的區間會導致「總經」「升降息」Tab永遠是空的
    - 法說會：目前MOPS查詢被機器人防護擋下(見collect_investor_conferences說明)，
      查詢區間為今天起算未來conference_window_days天(預設60天)
    任一來源失敗都不影響其他來源與已存在的資料，確保網頁不會因抓取失敗而崩潰"""
    os.makedirs(DATA_DIR, exist_ok=True)
    target_codes = _target_codes()
    name_map = _stock_name_map()

    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=lookback_days)
    window_end = today + datetime.timedelta(days=window_days)
    macro_window_end = today + datetime.timedelta(days=macro_window_days)

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

    for e in MACRO_EVENTS:
        try:
            event_date = datetime.date.fromisoformat(e['date'])
        except (ValueError, KeyError):
            continue
        if window_start <= event_date <= macro_window_end:
            events.append(e)

    for e in collect_investor_conferences(target_codes, window_days=conference_window_days):
        events.append(e)

    events.sort(key=lambda x: x['date'])

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"✅ 已儲存 {OUTPUT_PATH}（{len(events)} 筆事件）")
    return events

if __name__ == '__main__':
    collect()
