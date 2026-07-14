import json
import time
import logging
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

MIS_BASE = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
MIS_PRIMING_URL = "https://mis.twse.com.tw/stock/"
BATCH_SIZE = 20
BATCH_DELAY = 3
MAX_CONSECUTIVE_FAILURES = 3

# 大盤指數對應 MIS 查詢代號
INDEX_QUOTE_CODES = {
    "TWII": "tse_t00.tw",    # 加權指數
    "TWOII": "otc_o00.tw",   # 櫃買指數
}

_consecutive_failures = 0

def is_fallback_active():
    """連續失敗達上限時回傳 True，呼叫端應改用 yfinance 模式"""
    return _consecutive_failures >= MAX_CONSECUTIVE_FAILURES

def _record_failure(reason):
    global _consecutive_failures
    _consecutive_failures += 1
    logging.warning(f"⚠️  MIS 即時報價失敗（連續 {_consecutive_failures} 次）: {reason}")
    if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        logging.warning("⚠️  MIS 即時報價連續失敗達上限，自動退回 yfinance 模式")

def _record_success():
    global _consecutive_failures
    _consecutive_failures = 0

def _priming_session():
    """MIS 部分環境會需要先建立 session cookie 才能查詢，這裡預先 GET 一次首頁，
    失敗也不影響後續查詢（實測目前 API 即使沒有 cookie 也能正常回應）"""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(MIS_PRIMING_URL, timeout=10)
    except Exception as e:
        logging.warning(f"⚠️  MIS session 初始化失敗（將直接嘗試查詢）: {e}")
    return session

def _symbol_to_ex_ch(symbol):
    """config.py 代號格式 -> MIS 查詢格式：2330.TW -> tse_2330.tw，5347.TWO -> otc_5347.tw"""
    if symbol.endswith('.TWO'):
        return f"otc_{symbol[:-4]}.tw"
    return f"tse_{symbol.replace('.TW', '')}.tw"

def _parse_quote(item):
    """解析單檔 msgArray 項目，z 為 '-' 代表這個瞬間沒有新成交價，回傳 None 表示無可用資料"""
    z, y = item.get('z'), item.get('y')
    if not z or z == '-' or not y or y == '-':
        return None
    try:
        price = float(z)
        prev_close = float(y)
    except (TypeError, ValueError):
        return None
    if prev_close <= 0:
        return None
    change_pct = round((price - prev_close) / prev_close * 100, 2)
    try:
        volume = int(item.get('v', '0')) * 1000  # MIS v 為累計成交「張」數，換算成股數與 yfinance 口徑一致
    except (TypeError, ValueError):
        volume = 0
    return {
        "price": round(price, 2),
        "change_pct": change_pct,
        "volume": volume,
        "time": item.get('t', '')
    }

def fetch_quotes(symbols):
    """symbols: config.py 格式代號列表（如 '2330.TW'、'5347.TWO'）。
    回傳 {symbol: {price, change_pct, volume, time}}，查無即時成交價的股票不會出現在結果中。
    連續失敗達上限時直接回傳空字典，呼叫端應自行退回 yfinance 模式。"""
    if is_fallback_active():
        logging.warning("⚠️  MIS 連續失敗已達上限，跳過即時報價查詢，請改用 yfinance 模式")
        return {}

    ex_ch_map = {_symbol_to_ex_ch(s): s for s in symbols}
    ex_ch_list = list(ex_ch_map.keys())
    session = _priming_session()
    results = {}

    for i in range(0, len(ex_ch_list), BATCH_SIZE):
        batch = ex_ch_list[i:i + BATCH_SIZE]
        ex_ch = '|'.join(batch)
        try:
            r = session.get(MIS_BASE, params={'ex_ch': ex_ch, 'json': '1', 'delay': '0'}, timeout=15)
            r.raise_for_status()
            data = json.loads(r.text.strip())
            if data.get('rtcode') != '0000' or data.get('msgArray') is None:
                raise ValueError(f"rtcode={data.get('rtcode')}, msgArray={data.get('msgArray')}")

            for item in data['msgArray']:
                ex, ch = item.get('ex'), item.get('ch')
                if not ex or not ch:
                    continue
                key = f"{ex}_{ch}"
                symbol = ex_ch_map.get(key)
                if not symbol:
                    continue
                quote = _parse_quote(item)
                if quote:
                    results[symbol] = quote
            _record_success()
        except Exception as e:
            print(f"❌ MIS 即時報價批次抓取失敗，完整錯誤: {type(e).__name__}: {e}")
            _record_failure(str(e))
            if is_fallback_active():
                return results

        if i + BATCH_SIZE < len(ex_ch_list):
            time.sleep(BATCH_DELAY)

    return results

def fetch_index_quotes():
    """抓取加權指數/櫃買指數即時報價，回傳 {alias: {price, change_pct, time}}"""
    if is_fallback_active():
        return {}
    ex_ch_map = {v: k for k, v in INDEX_QUOTE_CODES.items()}
    session = _priming_session()
    results = {}
    try:
        ex_ch = '|'.join(INDEX_QUOTE_CODES.values())
        r = session.get(MIS_BASE, params={'ex_ch': ex_ch, 'json': '1', 'delay': '0'}, timeout=15)
        r.raise_for_status()
        data = json.loads(r.text.strip())
        if data.get('rtcode') != '0000' or data.get('msgArray') is None:
            raise ValueError(f"rtcode={data.get('rtcode')}")
        for item in data['msgArray']:
            ex, ch = item.get('ex'), item.get('ch')
            key = f"{ex}_{ch}"
            alias = ex_ch_map.get(key)
            if not alias:
                continue
            quote = _parse_quote(item)
            if quote:
                results[alias] = quote
        _record_success()
    except Exception as e:
        print(f"❌ MIS 大盤指數即時報價抓取失敗，完整錯誤: {type(e).__name__}: {e}")
        _record_failure(str(e))
    return results
