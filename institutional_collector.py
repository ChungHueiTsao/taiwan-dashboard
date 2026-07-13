import json
import os
import time
import datetime
import requests
import urllib3
from config import SECTORS

DATA_DIR = 'data'
OUTPUT_PATH = f'{DATA_DIR}/institutional.json'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# TPEx 的伺服器憑證缺少 Subject Key Identifier 擴充欄位（伺服器端設定問題，非我方風險），
# Python 3.13 的 OpenSSL 3.x 對此會嚴格拒絕連線（瀏覽器/curl 用各家系統信任鏈較寬鬆能正常連線）。
# 降低 SECLEVEL 測試後仍無法解決（該檢查與 SECLEVEL 無關），因此僅對 TPEx 這個已知有問題的網域
# 停用憑證驗證；抓的是公開的三大法人買賣超資料，非帳號/交易等敏感操作。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _session():
    return requests.Session()

def _target_codes():
    """只保留 config.py SECTORS 內出現的股票代號（去掉 .TW/.TWO 後綴）"""
    codes = set()
    for info in SECTORS.values():
        for symbol in info['stocks']:
            codes.add(symbol.replace('.TWO', '').replace('.TW', ''))
    return codes

def _to_int(s):
    try:
        return int(str(s).replace(',', ''))
    except (ValueError, TypeError):
        return 0

def fetch_twse_day(session, date_obj, target_codes):
    """上市：TWSE T86 三大法人買賣超日報，回傳 {code: {foreign, trust, dealer}} 或 None（該日無資料/例假日）"""
    date_str = date_obj.strftime('%Y%m%d')
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"❌ TWSE {date_str} 抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None

    if data.get('stat') != 'OK' or not data.get('data'):
        print(f"⚠️  TWSE {date_str} 無資料（可能為假日）：{data.get('stat')}")
        return None

    result = {}
    for row in data['data']:
        code = row[0].strip()
        if code not in target_codes:
            continue
        foreign_net = _to_int(row[4]) + _to_int(row[7])
        trust_net = _to_int(row[10])
        dealer_net = _to_int(row[11])
        result[code] = {"foreign": foreign_net, "trust": trust_net, "dealer": dealer_net}
    return result

def fetch_tpex_day(session, date_obj, target_codes):
    """上櫃：TPEx 三大法人買賣明細，回傳 {code: {foreign, trust, dealer}} 或 None（該日無資料/例假日）"""
    date_str = date_obj.strftime('%Y/%m/%d')
    url = f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={date_str}&response=json"
    try:
        r = session.get(url, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"❌ TPEx {date_str} 抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        return None

    tables = data.get('tables') or []
    if not tables or not tables[0].get('data'):
        print(f"⚠️  TPEx {date_str} 無資料（可能為假日）")
        return None

    result = {}
    for row in tables[0]['data']:
        code = row[0].strip()
        if code not in target_codes:
            continue
        foreign_net = _to_int(row[10])
        trust_net = _to_int(row[13])
        dealer_net = _to_int(row[22])
        result[code] = {"foreign": foreign_net, "trust": trust_net, "dealer": dealer_net}
    return result

def _inst_signal(foreign_5d, trust_5d):
    if foreign_5d > 0 and trust_5d > 0:
        return "法人同買"
    elif trust_5d > 0:
        return "投信布局"
    elif foreign_5d > 0:
        return "外資買超"
    elif foreign_5d < 0 and trust_5d < 0:
        return "法人調節"
    return "中性"

def collect(days_needed=5, max_lookback=15):
    """抓取最近 days_needed 個交易日的三大法人買賣超，存到 data/institutional.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    session = _session()
    target_codes = _target_codes()

    accumulated = {code: {"foreign": 0, "trust": 0, "dealer": 0} for code in target_codes}
    valid_days = 0
    cursor = datetime.date.today()
    lookback = 0

    while valid_days < days_needed and lookback < max_lookback:
        if cursor.weekday() >= 5:  # 週六日直接跳過，不耗用 API 呼叫
            cursor -= datetime.timedelta(days=1)
            lookback += 1
            continue

        print(f"\n📅 抓取 {cursor} 三大法人資料...")
        twse_data = fetch_twse_day(session, cursor, target_codes)
        time.sleep(3)
        tpex_data = fetch_tpex_day(session, cursor, target_codes)
        time.sleep(3)

        if twse_data is None and tpex_data is None:
            # 兩邊都沒資料，視為非交易日（國定假日），往前一天，不計入 valid_days
            cursor -= datetime.timedelta(days=1)
            lookback += 1
            continue

        for code, vals in (twse_data or {}).items():
            accumulated[code]["foreign"] += vals["foreign"]
            accumulated[code]["trust"] += vals["trust"]
            accumulated[code]["dealer"] += vals["dealer"]
        for code, vals in (tpex_data or {}).items():
            accumulated[code]["foreign"] += vals["foreign"]
            accumulated[code]["trust"] += vals["trust"]
            accumulated[code]["dealer"] += vals["dealer"]

        valid_days += 1
        cursor -= datetime.timedelta(days=1)
        lookback += 1

    if valid_days == 0:
        print("⚠️  完全沒有抓到任何交易日資料，保留舊的 data/institutional.json（如果有）")
        return None

    stocks = {}
    for code, vals in accumulated.items():
        foreign_5d = round(vals["foreign"] / 1000)
        trust_5d = round(vals["trust"] / 1000)
        dealer_5d = round(vals["dealer"] / 1000)
        stocks[code] = {
            "foreign_5d": foreign_5d,
            "trust_5d": trust_5d,
            "dealer_5d": dealer_5d,
            "inst_signal": _inst_signal(foreign_5d, trust_5d)
        }

    result = {
        "updated_at": datetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
        "trading_days_used": valid_days,
        "stocks": stocks
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已儲存 {OUTPUT_PATH}（{valid_days} 個交易日，{len(stocks)} 檔股票）")
    return result

if __name__ == '__main__':
    collect()
