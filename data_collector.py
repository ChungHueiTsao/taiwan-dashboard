import yfinance as yf
import pandas as pd
import json
import os
import base64
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz
from config import SECTORS

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
DATA_DIR = 'data'
HIST_PATH = f'{DATA_DIR}/history.csv'
KLINE_DIR = f'{DATA_DIR}/kline'
INSTITUTIONAL_PATH = f'{DATA_DIR}/institutional.json'

# 大盤指數對應：台指期沒有可靠的免費歷史資料來源，用加權指數代替
INDEX_SYMBOLS = {
    "加權指數": "^TWII",
    "OTC 櫃買": "^TWOII",
    "台指期": "^TWII"
}

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(KLINE_DIR, exist_ok=True)

def _github_config():
    """讀取用來持久化 history.csv 的 GitHub 設定（未設定則停用此功能）"""
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not token or not repo:
        return None
    return {
        "token": token,
        "repo": repo,
        "branch": os.environ.get('GITHUB_BRANCH', 'master'),
        "url": f"https://api.github.com/repos/{repo}/contents/data/history.csv"
    }

def restore_history_from_github():
    """開機時若本機沒有 history.csv（免費方案磁碟不持久），從 GitHub repo 還原"""
    if os.path.exists(HIST_PATH):
        return
    cfg = _github_config()
    if not cfg:
        return
    try:
        r = requests.get(cfg['url'], headers={"Authorization": f"token {cfg['token']}"},
                          params={"ref": cfg['branch']}, timeout=10)
        if r.status_code == 200:
            ensure_dirs()
            with open(HIST_PATH, 'wb') as f:
                f.write(base64.b64decode(r.json()['content']))
            print("✅ 已從 GitHub 還原歷史資料 data/history.csv")
    except Exception as e:
        print(f"⚠️  從 GitHub 還原歷史資料失敗: {e}")

def push_history_to_github():
    """把最新的 history.csv 推回 GitHub repo，避免免費方案重啟後資料遺失"""
    cfg = _github_config()
    if not cfg or not os.path.exists(HIST_PATH):
        return
    headers = {"Authorization": f"token {cfg['token']}"}
    try:
        with open(HIST_PATH, 'rb') as f:
            content_b64 = base64.b64encode(f.read()).decode()
        sha = None
        r = requests.get(cfg['url'], headers=headers, params={"ref": cfg['branch']}, timeout=10)
        if r.status_code == 200:
            sha = r.json().get('sha')
        payload = {
            "message": f"chore: 更新歷史資料 {datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}",
            "content": content_b64,
            "branch": cfg['branch']
        }
        if sha:
            payload["sha"] = sha
        put_r = requests.put(cfg['url'], headers=headers, json=payload, timeout=15)
        if put_r.status_code in (200, 201):
            print("✅ 已將歷史資料同步回 GitHub")
        else:
            print(f"⚠️  同步歷史資料到 GitHub 失敗: {put_r.status_code} {put_r.text[:200]}")
    except Exception as e:
        print(f"⚠️  同步歷史資料到 GitHub 發生錯誤: {e}")

# ---------------------------------------------------------------------------
# 升級1：真實K線資料
# ---------------------------------------------------------------------------

def _kline_path(symbol):
    return f'{KLINE_DIR}/{symbol}.json'

def get_kline_history(symbol, period='1y'):
    """抓取真實日K線（開高低收量），存成 data/kline/{symbol}.json 並回傳"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return None
        # 少數交易日資料缺漏（開高低收 NaN）直接丟棄該日；成交量缺漏（常見於指數）補0，
        # 避免 int(NaN) 造成整個更新流程崩潰
        hist = hist.dropna(subset=['Open', 'High', 'Low', 'Close'])
        if hist.empty:
            return None
        volume = hist['Volume'].fillna(0)
        kline = {
            "dates": hist.index.strftime('%Y-%m-%d').tolist(),
            "open": [round(float(x), 2) for x in hist['Open']],
            "high": [round(float(x), 2) for x in hist['High']],
            "low": [round(float(x), 2) for x in hist['Low']],
            "close": [round(float(x), 2) for x in hist['Close']],
            "volume": [int(x) for x in volume]
        }
        ensure_dirs()
        with open(_kline_path(symbol), 'w', encoding='utf-8') as f:
            json.dump(kline, f, ensure_ascii=False)
        return kline
    except Exception as e:
        print(f"  ⚠️  {symbol} K線抓取失敗: {e}")
        return None

def load_cached_kline(symbol):
    """讀取本機快取的K線，沒有就回傳 None（由呼叫端決定是否即時抓取）"""
    path = _kline_path(symbol)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def collect_index_klines():
    """抓取大盤三個 Tab 對應的指數K線（加權指數/OTC櫃買/台指期→用加權指數代替），平行抓取加速"""
    unique_symbols = list(dict.fromkeys(INDEX_SYMBOLS.values()))
    labels = {v: k for k, v in INDEX_SYMBOLS.items()}
    with ThreadPoolExecutor(max_workers=len(unique_symbols)) as executor:
        futures = {executor.submit(get_kline_history, symbol): symbol for symbol in unique_symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            kline = future.result()
            if kline:
                print(f"  ✅ {labels[symbol]}({symbol}) 指數K線已更新，共 {len(kline['dates'])} 筆")
            else:
                print(f"  ⚠️  {labels[symbol]}({symbol}) 指數K線抓取失敗")

# ---------------------------------------------------------------------------
# 升級4：ATR + 支撐壓力 建議價格計算
# ---------------------------------------------------------------------------

def calc_ma(values, n):
    if not values:
        return 0
    if len(values) < n:
        return sum(values) / len(values)
    return sum(values[-n:]) / n

def calc_atr(highs, lows, closes, period=14):
    """ATR(14)：用真實高低收價計算，不做還原股價調整（yfinance 的 Close 已含股利調整選項關閉，
    除權息當日可能出現價格跳空，這裡直接用原始高低收，屬已知限制"""
    if len(closes) < 2:
        return 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    window = trs[-period:] if len(trs) >= period else trs
    return round(sum(window) / len(window), 2) if window else 0

def calc_suggestion(kline, volume_ratio, inst_signal=None):
    """依 ATR + 支撐壓力 + 盈虧比計算進場/停損/目標與操作建議"""
    closes = kline['close']
    highs = kline['high']
    lows = kline['low']
    price = closes[-1]

    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    atr14 = calc_atr(highs, lows, closes, 14)
    low20 = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    high60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)

    # 進場價：支撐位 = max(近20日最低點, MA20)
    support = max(low20, ma20)
    entry_low = round(support * 1.00, 2)
    entry_high = round(support * 1.02, 2)
    entry_mid = round((entry_low + entry_high) / 2, 2)

    # 停損價：支撐位結合法，與 -8% 上限取較嚴格（較高）者
    stop_atr = low20 - 0.5 * atr14
    stop_pct_limit = entry_mid * 0.92
    stop = round(max(stop_atr, stop_pct_limit), 2)

    # 目標價：盈虧比法，壓力位 = 近60日最高點
    resistance = high60
    risk = entry_mid - stop
    reward_target = entry_mid + 2 * risk if risk > 0 else entry_mid
    target = round(min(resistance, reward_target), 2)

    rr_ok = True
    if risk > 0:
        rr_ratio = (target - entry_mid) / risk
        rr_ok = rr_ratio >= 2.0 - 1e-6
    else:
        rr_ok = False

    # 操作建議判斷（依嚴重度由高至低）
    if price < ma60:
        action = "弱勢，暫不介入"
    elif price < ma20:
        action = "觀望，等站回月線"
    elif volume_ratio > 1.5:
        action = "突破觀察"
    elif volume_ratio < 1.0:
        action = "回測支撐布局"
    else:
        action = "觀望，量能普通"

    # 升級5：籌碼加權（法人同買/調節 升降級）
    if inst_signal == "法人同買":
        if action == "突破觀察":
            action = "強勢買點（法人同買）"
        elif action == "回測支撐布局":
            action = "積極布局（法人同買）"
    elif inst_signal == "法人調節" and action in ("突破觀察", "回測支撐布局"):
        action = "觀望（法人調節中）"

    rr_ratio_display = round((target - entry_mid) / risk, 1) if risk > 0 else 0
    target_note = f"盈虧比 {rr_ratio_display}:1" if rr_ok else "盈虧比不足，不建議進場"

    if not rr_ok:
        action_note = "盈虧比不足，不建議進場"
    elif "突破" in action or "強勢買點" in action:
        action_note = "放量突破可追"
    elif "布局" in action:
        action_note = "回測支撐分批布局"
    elif "法人調節" in action:
        action_note = "籌碼轉弱，暫緩進場"
    elif "弱勢" in action:
        action_note = "跌破季線，暫不介入"
    else:
        action_note = "留意月線支撐，站回再評估"

    return {
        "entry": f"{entry_low}～{entry_high}",
        "entry_note": "支撐區進場" if price >= support else "跌破支撐，等待站回",
        "stop": str(stop),
        "stop_note": "支撐位-0.5ATR 與 -8% 取較嚴格者",
        "target": str(target) if rr_ok else "-",
        "target_note": target_note,
        "action": action,
        "action_note": action_note
    }

# ---------------------------------------------------------------------------
# 個股資料抓取（現價/漲跌幅 沿用K線資料，避免重複呼叫 yfinance）
# ---------------------------------------------------------------------------

def _load_institutional():
    if not os.path.exists(INSTITUTIONAL_PATH):
        return {}
    try:
        with open(INSTITUTIONAL_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('stocks', {})
    except Exception:
        return {}

def get_stock_data(symbol, inst_map=None):
    """抓取單一股票資料：現價/漲跌幅取自真實K線，並計算 ATR 支撐壓力建議"""
    kline = get_kline_history(symbol)
    if not kline or len(kline['close']) == 0:
        return None
    closes = kline['close']
    volumes = kline['volume']
    price = closes[-1]
    prev_price = closes[-2] if len(closes) > 1 else price
    change_pct = round((price - prev_price) / prev_price * 100, 2) if prev_price > 0 else 0
    volume = volumes[-1]
    tail5 = volumes[-5:] if len(volumes) >= 5 else volumes
    avg_volume = int(sum(tail5) / len(tail5)) if tail5 else volume
    volume_ratio = round(volume / avg_volume, 2) if avg_volume > 0 else 1.0

    bare_code = symbol.replace('.TWO', '').replace('.TW', '')
    inst = (inst_map or {}).get(bare_code, {})
    inst_signal = inst.get('inst_signal')

    suggestion = calc_suggestion(kline, volume_ratio, inst_signal)

    return {
        "price": price,
        "change_pct": change_pct,
        "volume": volume,
        "volume_ratio": volume_ratio,
        "foreign_5d": inst.get('foreign_5d', 0),
        "trust_5d": inst.get('trust_5d', 0),
        "inst_signal": inst_signal or "中性",
        **suggestion
    }

def collect_all():
    """抓取所有族群股票資料"""
    ensure_dirs()
    restore_history_from_github()
    now = datetime.now(TAIPEI_TZ)
    print(f"\n🚀 開始抓取資料 {now.strftime('%Y/%m/%d %H:%M')}")

    print("\n📈 更新大盤指數K線...")
    collect_index_klines()

    inst_map = _load_institutional()

    # 平行抓取所有股票資料（I/O bound，用 thread pool 大幅縮短抓取時間）
    all_symbols = [symbol for info in SECTORS.values() for symbol in info['stocks']]
    print(f"\n⏳ 平行抓取 {len(all_symbols)} 檔股票資料中...")
    stock_results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_stock_data, symbol, inst_map): symbol for symbol in all_symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                stock_results[symbol] = future.result()
            except Exception as e:
                print(f"  ⚠️  {symbol} 執行緒抓取例外: {e}")
                stock_results[symbol] = None

    result = {
        "updated_at": now.strftime('%Y/%m/%d %H:%M'),
        "sectors": {}
    }

    history_rows = []

    for sector_name, sector_info in SECTORS.items():
        print(f"\n📊 {sector_info['emoji']} {sector_name}")
        stocks_data = {}
        changes = []

        for symbol in sector_info['stocks']:
            name = sector_info['names'].get(symbol, symbol)
            data = stock_results.get(symbol)
            if data:
                stocks_data[symbol] = {
                    "name": name,
                    **data
                }
                changes.append(data['change_pct'])
                status = "🔴" if data['change_pct'] > 0 else "🟢"
                print(f"  {status} {name}: {data['price']} ({data['change_pct']:+.2f}%) [{data['inst_signal']}]")
            else:
                stocks_data[symbol] = {
                    "name": name,
                    "price": 0,
                    "change_pct": 0,
                    "volume": 0,
                    "volume_ratio": 1.0,
                    "foreign_5d": 0,
                    "trust_5d": 0,
                    "inst_signal": "中性"
                }

        avg_change = round(sum(changes) / len(changes), 2) if changes else 0
        score = min(100, max(0, int(50 + avg_change * 10)))

        sorted_stocks = sorted(
            [(s, d) for s, d in stocks_data.items() if d['price'] > 0],
            key=lambda x: x[1]['change_pct'],
            reverse=True
        )
        top_stock = sorted_stocks[0][1]['name'] if sorted_stocks else "-"
        top_change = sorted_stocks[0][1]['change_pct'] if sorted_stocks else 0
        bot_stock = sorted_stocks[-1][1]['name'] if sorted_stocks else "-"

        result['sectors'][sector_name] = {
            "emoji": sector_info['emoji'],
            "avg_change": avg_change,
            "score": score,
            "top_stock": top_stock,
            "top_change": top_change,
            "bot_stock": bot_stock,
            "stocks": stocks_data
        }

        history_rows.append({
            "date": now.strftime('%Y-%m-%d'),
            "sector": sector_name,
            "avg_change": avg_change,
            "score": score
        })

    # 儲存 latest.json
    with open(f'{DATA_DIR}/latest.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已儲存 data/latest.json")

    # 追加 history.csv
    df_new = pd.DataFrame(history_rows)
    if os.path.exists(HIST_PATH):
        df_old = pd.read_csv(HIST_PATH)
        df_old = df_old[df_old['date'] != now.strftime('%Y-%m-%d')]
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_combined = df_new
    df_combined.tail(60 * len(SECTORS)).to_csv(HIST_PATH, index=False)
    print(f"✅ 已更新 data/history.csv")

    push_history_to_github()

    return result

# ---------------------------------------------------------------------------
# 升級3：盤中即時更新（輕量，只更新現價/漲跌幅，不重抓整年K線）
# ---------------------------------------------------------------------------

def refresh_intraday_prices():
    """用 1 分鐘盤中資料更新現價與漲跌幅，避免每次手動更新都重抓整年K線"""
    ensure_dirs()
    if not os.path.exists(f'{DATA_DIR}/latest.json'):
        return collect_all()

    with open(f'{DATA_DIR}/latest.json', 'r', encoding='utf-8') as f:
        result = json.load(f)

    now = datetime.now(TAIPEI_TZ)
    print(f"\n⏱️  盤中即時更新 {now.strftime('%Y/%m/%d %H:%M')}")

    for sector_name, sector_info in result.get('sectors', {}).items():
        changes = []
        for symbol, stock in sector_info.get('stocks', {}).items():
            try:
                ticker = yf.Ticker(symbol)
                intraday = ticker.history(period='1d', interval='1m')
                cached = load_cached_kline(symbol)
                if intraday.empty or not cached or not cached.get('close'):
                    changes.append(stock.get('change_pct', 0))
                    continue
                current_price = round(float(intraday['Close'].iloc[-1]), 2)
                prev_close = cached['close'][-1]
                change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
                stock['price'] = current_price
                stock['change_pct'] = change_pct
                stock['volume'] = int(intraday['Volume'].sum())
                changes.append(change_pct)
                print(f"  🔄 {stock.get('name', symbol)}: {current_price} ({change_pct:+.2f}%)")
            except Exception as e:
                print(f"  ⚠️  {symbol} 盤中資料抓取失敗: {e}")
                changes.append(stock.get('change_pct', 0))

        if changes:
            avg_change = round(sum(changes) / len(changes), 2)
            sector_info['avg_change'] = avg_change
            sector_info['score'] = min(100, max(0, int(50 + avg_change * 10)))
            sorted_stocks = sorted(
                [(s, d) for s, d in sector_info['stocks'].items() if d['price'] > 0],
                key=lambda x: x[1]['change_pct'],
                reverse=True
            )
            if sorted_stocks:
                sector_info['top_stock'] = sorted_stocks[0][1]['name']
                sector_info['top_change'] = sorted_stocks[0][1]['change_pct']
                sector_info['bot_stock'] = sorted_stocks[-1][1]['name']

    result['updated_at'] = now.strftime('%Y/%m/%d %H:%M')
    with open(f'{DATA_DIR}/latest.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已更新 data/latest.json（盤中即時價）")

    return result

if __name__ == '__main__':
    collect_all()
