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

def _sector_of(code):
    """反查某檔個股代號屬於哪個族群"""
    for sector_name, info in SECTORS.items():
        for sym in info['stocks']:
            if sym.replace('.TWO', '').replace('.TW', '') == code:
                return sector_name
    return None

def _sector_peers(code, sector_name):
    """同族群其他個股清單 [(code, name), ...]，不含自己"""
    if not sector_name or sector_name not in SECTORS:
        return []
    peers = []
    for sym in SECTORS[sector_name]['stocks']:
        peer_code = sym.replace('.TWO', '').replace('.TW', '')
        if peer_code != code:
            peers.append((peer_code, SECTORS[sector_name]['names'].get(sym, peer_code)))
    return peers

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
            events.append({"date": date_iso, "code": code, "kind": kind, "cash": cash})
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
            events.append({"date": date_iso, "code": code, "kind": kind, "cash": cash})
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

# 手動維護清單：目前沒有可靠自動化來源、需要人工補充的一次性事件（例如已知的個股法說會日期）。
# 格式需與其他事件來源一致，每筆事件都要有summary（禁止與title重複）+ related_stocks或affected_sectors其中一種：
#   個股類事件範例：
#   {"date": "2026-08-15", "type": "法說會", "title": "台積電法人說明會", "impact": "大",
#    "summary": "台積電召開法人說明會，公布上季財報與下季展望。市場關注重點：訂單能見度、資本支出計畫、"
#                "先進製程良率與產能利用率、毛利率展望。",
#    "related_stocks": [
#        {"stock": "2330", "sector": "神山群", "relation": "本尊", "impact": "法說會後股價波動",
#         "reason": "財測與展望優於或劣於市場預期會直接反映在隔日股價，需留意管理層對下季展望的用詞。"},
#        {"stock": "2303", "sector": "神山群", "relation": "同族群",
#         "impact": "同業比較基準",
#         "reason": "與台積電同屬神山群，法說會揭露的產業展望常被市場當作同業比較基準，帶動族群連動。"}
#    ]}
#   主題類事件範例（見MACRO_EVENTS的affected_sectors寫法）
MANUAL_EVENTS = []

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

def _rate_decision_affected_sectors(source_label):
    """升降息類事件（實際決策，如FOMC/央行理監事會議）的影響族群清單。
    資金成本敏感的成長型族群標記為negative（會前市場慣常關注的「風險族群」，
    reason中會同時說明偏鷹/偏鴿兩種情境，並非預測會議結果），
    內需/政策驅動型族群標記為neutral作對照組"""
    return [
        {"sector": "神山群", "direction": "negative",
         "reason": f"資本支出龐大、評價對折現率敏感：{source_label}決議偏鷹（利率維持高檔/延後降息）時評價壓力上升，偏鴿則可能受惠資金行情。"},
        {"sector": "IC設計", "direction": "negative",
         "reason": f"高本益比成長股，對利率環境敏感，{source_label}決議偏鷹時評價壓力較大，偏鴿則可能反彈。"},
        {"sector": "被動元件", "direction": "negative",
         "reason": f"終端需求循環股，{source_label}決議偏緊會抑制客戶備貨意願，估值同時受利率影響。"},
        {"sector": "記憶體", "direction": "negative",
         "reason": f"產業循環疊加高資本支出，{source_label}政策走向影響資金去化速度與客戶庫存政策。"},
        {"sector": "重電", "direction": "neutral",
         "reason": f"訂單主要來自國內電網更新與電力建設需求，由政策與基礎建設驅動，非{source_label}單次決策直接影響，可作對照組。"},
        {"sector": "PCB/CCL", "direction": "neutral",
         "reason": "接單能見度主要看終端電子產品需求循環，對單次利率決策的直接連動較低，可作對照組。"},
    ]

def _macro_data_affected_sectors(data_label):
    """總經數據公布類事件（非決策，只是影響市場對政策路徑的預期，如CPI/非農）的影響族群清單"""
    return [
        {"sector": "神山群", "direction": "negative",
         "reason": f"{data_label}優於預期會強化市場對利率維持高檔的預期，推升折現率，壓抑高評價成長股；數據疲弱則相反。"},
        {"sector": "IC設計", "direction": "negative",
         "reason": f"高本益比成長股對利率預期敏感，{data_label}公布後常見評價波動。"},
        {"sector": "被動元件", "direction": "negative",
         "reason": f"終端需求循環股，{data_label}反映的景氣強弱牽動客戶備貨與庫存政策。"},
        {"sector": "記憶體", "direction": "negative",
         "reason": f"產業循環股，{data_label}反映的景氣冷熱影響終端庫存去化速度。"},
        {"sector": "重電", "direction": "neutral",
         "reason": "訂單主要來自國內電網更新與電力建設需求，由政策與基礎建設驅動，短期對單次總經數據的直接連動較低，可作對照組。"},
        {"sector": "PCB/CCL", "direction": "neutral",
         "reason": "接單能見度主要看終端電子產品需求循環，對單次總經數據公布的直接連動較低，可作對照組。"},
    ]

# 景氣對策信號燈號對照表（分數區間、市場解讀）
BUSINESS_SIGNAL_LIGHTS = [
    ("🔴 紅燈", "38-45分", "景氣熱絡"),
    ("🟠 黃紅燈", "32-37分", "景氣轉向"),
    ("🟢 綠燈", "23-31分", "景氣穩定"),
    ("🔵 黃藍燈", "17-22分", "景氣欠佳"),
    ("🔷 藍燈", "9-16分", "景氣低迷"),
]

def _build_macro_events(year=2026):
    events = []
    for d in _FOMC_DATES_2026:
        if datetime.date.fromisoformat(d).year == year:
            events.append({
                "date": d, "type": "升降息", "title": "美國聯準會FOMC利率決議", "impact": "極大",
                "summary": "本次會議公布最新聯邦資金利率決策，並由主席召開記者會說明後續政策方向。市場影響機制分兩層："
                           "利率決策本身立即改變資金成本與美元匯率；記者會中對通膨、就業與未來升降息路徑的用詞"
                           "（鷹派/鴿派）則主導後續數週的風險偏好與資金流向，兩者往往比決策本身更牽動台股類股表現。",
                "affected_sectors": _rate_decision_affected_sectors("Fed")
            })
    for d in _CBC_DATES_2026:
        if datetime.date.fromisoformat(d).year == year:
            events.append({
                "date": d, "type": "升降息", "title": "台灣央行理監事會議", "impact": "大",
                "summary": "央行公布重貼現率決議與貨幣政策展望，並於會後記者會說明。決策本身直接影響台幣資金成本與"
                           "房市/企業放款利率；記者會對匯率與通膨態度的表述，則牽動台幣匯率與外資對台股的資金流向，"
                           "兩者影響時間軸不同。",
                "affected_sectors": _rate_decision_affected_sectors("央行")
            })
    for d in _US_CPI_DATES_2026:
        if datetime.date.fromisoformat(d).year == year:
            events.append({
                "date": d, "type": "總經", "title": "美國CPI消費者物價指數公布", "impact": "大",
                "summary": "公布美國最新月度通膨數據，是市場評估Fed後續利率路徑最重要的單一數據之一。若數據高於預期，"
                           "市場會下修降息機率、推升美元與美債殖利率；若低於預期則相反。公布後短時間內台股夜盤期貨與ADR"
                           "常有較大波動，隔日台股開盤易受影響。",
                "affected_sectors": _macro_data_affected_sectors("CPI數據")
            })
    for month in range(1, 13):
        nfp_date = _nth_weekday(year, month, 4, 1)  # 週五=4，每月第一個週五
        events.append({
            "date": nfp_date.isoformat(), "type": "總經", "title": "美國非農就業數據公布", "impact": "大",
            "summary": "公布美國最新月度非農就業人數、失業率與時薪年增率，是判斷美國勞動市場強弱與消費動能的關鍵指標，"
                       "也是Fed評估通膨黏著度的重要依據。就業數據強勁通常降低降息急迫性，數據疲弱則提高降息預期，"
                       "兩者都會透過利率預期間接影響台股類股表現。",
            "affected_sectors": _macro_data_affected_sectors("非農就業數據")
        })
        signal_date = datetime.date(year, month, 27)
        lights_desc = "、".join(f"{name}({score}，{desc})" for name, score, desc in BUSINESS_SIGNAL_LIGHTS)
        events.append({
            "date": signal_date.isoformat(), "type": "總經", "title": "台灣景氣對策信號公布", "impact": "中",
            "summary": f"國發會每月公布景氣對策信號燈號，以9項指標構成綜合分數，並以5種燈號呈現景氣循環位置："
                       f"{lights_desc}。燈號轉強通常對應內需與景氣循環股偏多，燈號轉弱則反映景氣降溫訊號。"
                       f"目前實際公布燈號請至國發會網站查詢最新數據（本清單僅為排程提醒日期，非即時分數）。",
            "affected_sectors": [
                {"sector": "被動元件", "direction": "neutral",
                 "reason": "下游應用廣泛，景氣對策信號屬於落後與同步指標綜合，燈號轉強(轉紅)通常對應終端拉貨轉強，"
                           "轉弱(轉藍)則反映需求降溫，實際方向需待當期數據公布判斷。"},
                {"sector": "功率元件", "direction": "neutral",
                 "reason": "需求與整體工業生產、消費性電子景氣連動，景氣對策信號屬於觀察整體景氣循環位置的指標，"
                           "燈號變化方向需待實際公布判斷。"},
                {"sector": "PCB/CCL", "direction": "neutral",
                 "reason": "接單能見度反映電子產業出口動能，與景氣對策信號中的出口值、工業生產等分項指標相關性高，"
                           "方向需待數據公布判斷。"},
                {"sector": "重電", "direction": "neutral",
                 "reason": "訂單主要來自國內電網更新與電力建設需求，由政策與長期基礎建設驅動，"
                           "與單月景氣對策信號的連動性較低，可作對照組。"},
            ]
        })
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
        if not code:
            continue
        name = name_map.get(code, code)
        cash = e.get('cash', 0)
        kind = e.get('kind', '除權息')
        sector_name = _sector_of(code)

        related_stocks = [{
            "stock": code, "sector": sector_name or '', "relation": "本尊",
            "impact": "短線除息缺口",
            "reason": f"實際配息{cash}元，除息當日參考價會直接扣減對應金額，形成除息缺口，"
                      f"缺口是否回補（填息）視除息後買盤力道與大盤環境而定。"
        }]
        for peer_code, peer_name in _sector_peers(code, sector_name):
            related_stocks.append({
                "stock": peer_code, "sector": sector_name, "relation": "同族群",
                "impact": "資金效應",
                "reason": f"與{name}同屬{sector_name}族群，除息前後市場資金可能在族群內部短暫輪動，"
                          f"無直接關聯，僅供對照。"
            })

        events.append({
            "date": e['date'],
            "type": "除權息",
            "title": f"{name} {kind} 現金股利{cash}元".strip(),
            "impact": "中",
            "summary": f"{name}將於{e['date']}除息，現金股利{cash}元。除息參考價＝除息前一交易日收盤價－{cash}元"
                       f"（若另含股票股利則需一併計入）。除息後股價若回填至除息前水準稱為「填息」，反之則為「貼息」，"
                       f"填息速度與大盤量能、族群輪動及公司基本面有關，建議除息前後留意成交量變化與族群強弱排行。",
            "related_stocks": related_stocks
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
