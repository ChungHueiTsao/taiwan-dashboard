import json
import os
import pandas as pd


def _load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _load_history_scores():
    """族群評分近20日歷史（首頁/產業排行頁的趨勢小圖用）"""
    history_data = {}
    try:
        df = pd.read_csv('data/history.csv')
        for sector in df['sector'].unique():
            sd = df[df['sector'] == sector].tail(20)
            history_data[sector] = {"dates": sd['date'].tolist(), "scores": sd['score'].tolist()}
    except Exception:
        pass
    return history_data


def _load_institutional_history():
    """個股頁籌碼分析Tab的法人買賣超趨勢圖：{code: [{date,foreign,trust,dealer}, ...]}"""
    result = {}
    try:
        df = pd.read_csv('data/institutional_history.csv', dtype={"code": str})
        for code, g in df.groupby('code'):
            g = g.sort_values('date')
            result[code] = [
                {"date": r.date, "foreign": int(r.foreign), "trust": int(r.trust), "dealer": int(r.dealer)}
                for r in g.itertuples()
            ]
    except Exception:
        pass
    return result


def _latest_day_institutional_total(inst_history):
    """首頁「三大法人今日合計」：取每檔股票在歷史裡最新一天的資料加總（不是5日累計）"""
    latest_date = None
    for rows in inst_history.values():
        if rows and (latest_date is None or rows[-1]['date'] > latest_date):
            latest_date = rows[-1]['date']
    if not latest_date:
        return None
    totals = {"date": latest_date, "foreign": 0, "trust": 0, "dealer": 0}
    for rows in inst_history.values():
        if rows and rows[-1]['date'] == latest_date:
            totals['foreign'] += rows[-1]['foreign']
            totals['trust'] += rows[-1]['trust']
            totals['dealer'] += rows[-1]['dealer']
    return totals


def build_stock_js(sym, sd, sector_name, sector_emoji, fundamentals):
    """單一股票的完整前端資料物件：技術面建議/籌碼5日加總/基本面，所有頁面共用同一份格式"""
    p = sd.get('price', 0)
    c = sd.get('change_pct', 0)
    v = sd.get('volume', 0)
    vr = sd.get('volume_ratio', 1.0)
    c_sign = "+" if c > 0 else ""
    c_color = "true" if c > 0 else "false"
    foreign_5d = sd.get('foreign_5d', 0)
    trust_5d = sd.get('trust_5d', 0)
    inst_signal = sd.get('inst_signal', '中性')
    star = "⭐ " if inst_signal == "法人同買" else ""
    code_bare = sym.replace('.TWO', '').replace('.TW', '')
    fd = fundamentals.get(code_bare, {}) if fundamentals else {}

    return {
        "name": sd.get('name', sym),
        "code": code_bare,
        "code_bare": code_bare,
        "sym": sym,
        "price": str(p),
        "chg": f"{c_sign}{c:.2f}%",
        "vol": f"{v:,}",
        "vr": f"{vr:.1f}",
        "entry": sd.get('entry', '-'),
        "stop": sd.get('stop', '-'),
        "target": sd.get('target', '-'),
        "action": sd.get('action', '觀望'),
        "entryNote": sd.get('entry_note', ''),
        "stopNote": sd.get('stop_note', ''),
        "targetNote": sd.get('target_note', ''),
        "actionNote": sd.get('action_note', ''),
        "foreignFmt": f"{'+' if foreign_5d >= 0 else ''}{foreign_5d:,}張",
        "trustFmt": f"{'+' if trust_5d >= 0 else ''}{trust_5d:,}張",
        "foreignUp": "true" if foreign_5d >= 0 else "false",
        "trustUp": "true" if trust_5d >= 0 else "false",
        "foreign5d": foreign_5d,
        "trust5d": trust_5d,
        "instSignal": inst_signal,
        "star": star,
        "up": c_color,
        "sectorName": sector_name,
        "sectorEmoji": sector_emoji,
        "foreignTrust5d": foreign_5d + trust_5d,
        "volumeRatioRaw": vr,
        "changePctRaw": c,
        "priceRaw": p,
        # 基本面（best-effort，抓不到就是 null，前端顯示「-」）
        "pe": fd.get('pe'),
        "pb": fd.get('pb'),
        "dividendYield": fd.get('dividend_yield'),
        "eps": fd.get('eps'),
        "revenueYoy": fd.get('revenue_yoy'),
        "grossMargin": fd.get('gross_margin'),
        "operatingMargin": fd.get('operating_margin'),
    }


def generate():
    analysis = _load_json('data/analysis.json', {
        "updated_at": "載入中", "market_sentiment": {"label": "🟡 中性", "color": "#C9970C"},
        "up_count": 0, "flat_count": 0, "down_count": 0, "top_sector": "-", "sectors": []
    })
    history_scores = _load_history_scores()
    big_holders = _load_json('data/big_holders.json', None)
    fundamentals_doc = _load_json('data/fundamentals.json', {"stocks": {}})
    fundamentals = fundamentals_doc.get('stocks', {})
    events = _load_json('data/events.json', [])
    inst_history = _load_institutional_history()
    latest_inst_total = _latest_day_institutional_total(inst_history)

    sectors_raw = analysis.get('sectors', [])
    updated_at = analysis.get('updated_at', '載入中')
    sentiment = analysis.get('market_sentiment', {"label": "🟡 中性", "color": "#C9970C"})
    data_source = analysis.get('data_source', 'yfinance')
    delay_note = "盤中即時（延遲約5秒）" if data_source == 'realtime' else "資料延遲約15分鐘"

    # ---- 組出 ALL_STOCKS（全量個股）與 SECTORS（族群層級聚合，含熱力圖用的總量） ----
    all_stocks = {}
    sectors_payload = []
    for s in sectors_raw:
        stock_items = list(s.get('stocks', {}).items())
        total_volume = 0
        sector_stock_syms = []
        for sym, sd in stock_items:
            sj = build_stock_js(sym, sd, s['name'], s['emoji'], fundamentals)
            all_stocks[sym] = sj
            total_volume += sd.get('volume', 0)
            sector_stock_syms.append(sym)
        sectors_payload.append({
            "name": s['name'], "emoji": s['emoji'], "avgChange": s['avg_change'],
            "score": s['score'], "rating": s['rating'], "topStock": s.get('top_stock', '-'),
            "topChange": s.get('top_change', 0), "totalVolume": total_volume,
            "stocks": sector_stock_syms,
            "history": history_scores.get(s['name'], {"dates": [], "scores": []})
        })

    # 大戶動向：併入 all_stocks（沒有的股票就不加欄位，前端顯示「-」）
    if big_holders and big_holders.get('stocks'):
        for code, h in big_holders['stocks'].items():
            for sym, sj in all_stocks.items():
                if sj['code_bare'] == code:
                    sj['holderRatio'] = h.get('holder_ratio')
                    sj['holderRatioChange'] = h.get('ratio_change')

    # 事件：轉成前端可直接用的格式，並建立 code -> events 反查表（個股頁「新聞」Tab用）
    code_to_info = {sj['code_bare']: {
        "name": sj['name'], "sector": sj['sectorName'], "emoji": sj['sectorEmoji'], "symbol": sym
    } for sym, sj in all_stocks.items()}
    sector_emoji_map = {sj['sectorName']: sj['sectorEmoji'] for sj in all_stocks.values()}

    events_sorted = sorted(events, key=lambda e: e.get('date', ''))
    event_details = []
    for e in events_sorted:
        etype = e.get('type', '其他')
        impact_stocks = []
        for rs in e.get('related_stocks', []):
            code = rs.get('stock', '')
            info = code_to_info.get(code)
            if not info:
                continue
            impact_stocks.append({
                "code": code, "symbol": info['symbol'], "name": info['name'],
                "sector": info['emoji'] + info['sector'], "sectorName": info['sector'],
                "relation": rs.get('relation', ''), "impact": rs.get('impact', ''),
                "reason": rs.get('reason', '')
            })
        affected_sectors = []
        for asec in e.get('affected_sectors', []):
            sector_name = asec.get('sector', '')
            affected_sectors.append({
                "sector": sector_name, "sectorLabel": sector_emoji_map.get(sector_name, '') + sector_name,
                "direction": asec.get('direction', 'neutral'), "reason": asec.get('reason', '')
            })
        event_details.append({
            "date": e.get('date', ''), "type": etype, "title": e.get('title', ''),
            "summary": e.get('summary') or e.get('title', ''),
            "impactStocks": impact_stocks, "affectedSectors": affected_sectors
        })

    payload = {
        "updatedAt": updated_at,
        "delayNote": delay_note,
        "sentiment": sentiment,
        "upCount": analysis.get('up_count', 0),
        "downCount": analysis.get('down_count', 0),
        "flatCount": analysis.get('flat_count', 0),
        "topSector": analysis.get('top_sector', '-'),
        "sectors": sectors_payload,
        "allStocks": all_stocks,
        "events": event_details,
        "institutionalHistory": inst_history,
        "latestInstitutionalTotal": latest_inst_total,
    }
    dashboard_data_json = json.dumps(payload, ensure_ascii=False)

    os.makedirs('templates', exist_ok=True)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🇹🇼 台股籌碼站</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;700;900&family=Noto+Sans+TC:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/static/style.css">
<script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
</head>
<body>

<div class="nav">
  <div class="nav-left">
    <h1>🇹🇼 台股籌碼站</h1>
    <div class="nav-tabs">
      <button class="nav-tab active" id="nav-tab-home" onclick="showPage('home')">首頁</button>
      <button class="nav-tab" id="nav-tab-stock" onclick="showPage('stock')">個股</button>
      <button class="nav-tab" id="nav-tab-industry" onclick="showPage('industry')">產業排行</button>
      <button class="nav-tab" id="nav-tab-watch" onclick="showPage('watch')">自選股</button>
      <button class="nav-tab" id="nav-tab-events" onclick="showPage('events')">事件</button>
    </div>
  </div>
  <div class="nav-search">
    <input type="text" id="stock-search-input" placeholder="搜尋股票代碼或名稱" autocomplete="off">
    <div class="search-results" id="stock-search-results"></div>
  </div>
  <div class="meta">
    <span>最後更新：{updated_at}</span>
    <span style="font-size:9px;color:var(--ink-muted)">（{delay_note}）</span>
    <span class="badge" style="background:{sentiment['color']}22;color:{sentiment['color']};border:1px solid {sentiment['color']}44">{sentiment['label']}</span>
    <button class="btn-sm" onclick="location.href='/api/refresh?redirect=1'">🔄 立即更新</button>
  </div>
</div>

<!-- ============ 首頁 ============ -->
<section class="page active" id="page-home">
  <div class="stat-row" id="home-stats"></div>
  <div class="grid home-grid">
    <div class="side-stack">
      <div class="card">
        <div class="section-head padded"><h2>熱門個股</h2><span class="more" onclick="showPage('industry')">看產業排行 →</span></div>
        <table><thead><tr><th>股票</th><th>成交價</th><th>漲跌幅</th><th>成交量(張)</th><th>外資5日</th></tr></thead>
          <tbody id="home-hot-stocks"></tbody>
        </table>
      </div>
      <div class="card">
        <div class="section-head padded"><h2>產業強弱一覽</h2><span class="more" onclick="showPage('industry')">看完整產業排行 →</span></div>
        <div class="heatmap" id="home-heatmap"></div>
      </div>
    </div>
    <div class="side-stack">
      <div class="card">
        <div class="section-head padded"><h2>最新事件</h2></div>
        <div id="home-events"></div>
      </div>
    </div>
  </div>
</section>

<!-- ============ 個股頁 ============ -->
<section class="page" id="page-stock">
  <div id="stock-empty" class="card padded" style="text-align:center;padding:60px 20px;color:var(--ink-faint)">
    請用上方搜尋框查詢股票，或從首頁／產業排行／自選股點選個股
  </div>
  <div id="stock-content" style="display:none">
    <div class="card stock-header">
      <div class="sh-left">
        <span class="sh-name" id="sh-name">-</span>
        <span class="sh-code mono" id="sh-code">-</span>
        <span class="sh-price mono" id="sh-price">-</span>
        <span class="sh-chg" id="sh-chg">-</span>
      </div>
      <div class="sh-meta">
        <span>成交量 <b id="sh-vol">-</b> 張</span>
        <span>量比 <b id="sh-vr">-</b></span>
        <span>本益比 <b id="sh-pe">-</b></span>
      </div>
      <div class="sh-actions"><button class="btn-sm" id="sh-watch-btn" onclick="toggleWatch()">＋ 加入自選</button></div>
    </div>

    <div class="subtabbar">
      <button class="active" data-sub="tech" onclick="switchStockTab(this,'tech')">技術分析</button>
      <button data-sub="chip" onclick="switchStockTab(this,'chip')">籌碼分析</button>
      <button data-sub="fund" onclick="switchStockTab(this,'fund')">基本面</button>
      <button data-sub="news" onclick="switchStockTab(this,'news')">新聞</button>
    </div>

    <div class="subpage active" id="sub-tech">
      <div class="card">
        <div class="period-row">
          <button class="period-btn active" onclick="setPeriod(this)">日</button>
          <button class="period-btn" onclick="setPeriod(this)">週</button>
          <button class="period-btn" onclick="setPeriod(this)">月</button>
          <div style="width:1px;height:14px;background:var(--border);margin:0 4px"></div>
          <div class="ind-row">
            <span><span class="dot" style="background:var(--fast)"></span>MA5</span>
            <span><span class="dot" style="background:var(--slow)"></span>MA20</span>
            <span><span class="dot" style="background:var(--ma60)"></span>MA60</span>
            <span><span class="dot" style="background:var(--boll);opacity:.5"></span>布林帶</span>
          </div>
        </div>
        <div class="chart-main" id="chart-main">
          <div class="kline-info-bar" id="kline-info-bar">
            <span id="ki-date">-</span>
            <span>開 <b id="ki-open">-</b></span><span>高 <b id="ki-high">-</b></span>
            <span>低 <b id="ki-low">-</b></span><span>收 <b id="ki-close">-</b></span>
            <span style="color:var(--fast)">MA5 <b id="ki-ma5">-</b></span>
            <span style="color:var(--slow)">MA20 <b id="ki-ma20">-</b></span>
            <span style="color:var(--ma60)">MA60 <b id="ki-ma60">-</b></span>
            <span style="color:var(--boll)">布林上 <b id="ki-bollu">-</b></span>
            <span style="color:var(--boll)">布林下 <b id="ki-bolld">-</b></span>
            <span style="color:var(--fast)">K <b id="ki-k">-</b></span>
            <span style="color:var(--slow)">D <b id="ki-d">-</b></span>
            <span>量 <b id="ki-vol">-</b></span>
          </div>
          <div id="mainChart" style="width:100%;height:420px"></div>
        </div>
      </div>
      <div class="card padded" style="margin-top:16px">
        <div class="section-head" style="margin-bottom:10px"><h2 style="font-size:15px">技術面操作建議</h2></div>
        <div class="suggest-box">
          <div class="suggest-item"><div class="sl">📌 建議進場</div><div class="sv" style="color:var(--up)" id="s-entry">-</div><div class="st" id="s-entry-note">-</div></div>
          <div class="suggest-item"><div class="sl">🛑 停損價位</div><div class="sv" style="color:var(--down)" id="s-stop">-</div><div class="st" id="s-stop-note">-</div></div>
          <div class="suggest-item"><div class="sl">🎯 目標價位</div><div class="sv" style="color:var(--accent)" id="s-target">-</div><div class="st" id="s-target-note">-</div></div>
          <div class="suggest-item"><div class="sl">💡 操作建議</div><div class="sv" style="font-size:11px;color:var(--neutral)" id="s-action">-</div><div class="st" id="s-action-note">-</div></div>
        </div>
      </div>
    </div>

    <div class="subpage" id="sub-chip">
      <div class="two-col">
        <div class="card padded">
          <div class="section-head"><h2 style="font-size:15px">三大法人買賣超趨勢（近20日）</h2></div>
          <canvas id="chip-canvas" height="200"></canvas>
          <div style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:var(--ink-muted)">
            <div class="legend-line"><span class="legend-swatch" style="background:var(--fast)"></span>外資</div>
            <div class="legend-line"><span class="legend-swatch" style="background:var(--slow)"></span>投信</div>
            <div class="legend-line"><span class="legend-swatch" style="background:var(--ma60)"></span>自營商</div>
          </div>
        </div>
        <div class="card padded">
          <div class="section-head"><h2 style="font-size:15px">籌碼摘要</h2></div>
          <div class="kv-grid">
            <div class="kv-cell"><div class="k">外資5日</div><div class="v" id="chip-foreign">-</div></div>
            <div class="kv-cell"><div class="k">投信5日</div><div class="v" id="chip-trust">-</div></div>
            <div class="kv-cell"><div class="k">法人動向</div><div class="v" id="chip-signal">-</div></div>
            <div class="kv-cell"><div class="k">大戶持股比</div><div class="v" id="chip-holder">-</div></div>
          </div>
          <p style="font-size:11.5px;color:var(--ink-faint);margin-top:10px">分點買賣超尚未提供（需另外處理證交所驗證碼，列為未來獨立專案）。</p>
        </div>
      </div>
    </div>

    <div class="subpage" id="sub-fund">
      <div class="kv-grid" id="fund-grid"></div>
      <p style="font-size:11.5px;color:var(--ink-faint);margin-top:10px">資料來源：證交所/櫃買中心官方 OpenAPI。「-」代表該欄位暫無資料（例如虧損股本益比無意義、或該產業損益表格式與一般業不同）。</p>
    </div>

    <div class="subpage" id="sub-news">
      <div class="card" id="stock-news-list"></div>
    </div>
  </div>
</section>

<!-- ============ 產業排行 ============ -->
<section class="page" id="page-industry">
  <div class="section-head">
    <div><div class="eyebrow">產業排行</div><h2>類股強弱與資金流向</h2></div>
  </div>
  <div class="card" style="margin-bottom:16px"><div class="heatmap" id="industry-heatmap"></div></div>
  <div class="card">
    <table><thead><tr><th>產業別</th><th>漲跌幅</th><th>評分</th><th>成交量(張)</th><th>龍頭股</th></tr></thead>
      <tbody id="industry-table-body"></tbody>
    </table>
  </div>
</section>

<!-- ============ 自選股／篩選器 ============ -->
<section class="page" id="page-watch">
  <div class="two-col" style="align-items:start">
    <div class="card">
      <div class="section-head padded"><h2>我的自選股</h2></div>
      <table><thead><tr><th>股票</th><th>成交價</th><th>漲跌幅</th><th>本益比</th><th>操作</th></tr></thead>
        <tbody id="watch-body"></tbody>
      </table>
      <div id="watch-empty" class="rank-empty" style="display:none">尚未加入任何自選股，可從個股頁或下方篩選器加入</div>
    </div>
    <div class="card padded">
      <div class="section-head" style="margin-bottom:10px"><h2 style="font-size:15px">快速篩選器</h2></div>
      <div id="screener-chips" class="screener-chips"></div>
      <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
        <button class="btn-sm active-up" onclick="applyScreener()">套用篩選</button>
        <span id="screener-count" style="font-size:12px;color:var(--ink-muted)"></span>
      </div>
      <table style="margin-top:12px"><thead><tr><th>股票</th><th>成交價</th><th>漲跌幅</th><th></th></tr></thead>
        <tbody id="screener-body"></tbody>
      </table>
    </div>
  </div>
</section>

<!-- ============ 事件頁面 ============ -->
<section class="page" id="page-events">
  <div class="events-page-inner">
    <div class="ev-wrap">
      <div class="ev-timeline-panel">
        <div class="ev-filter-chips">
          <button class="ev-chip active" onclick="filterEvents(this,'全部')">全部</button>
          <button class="ev-chip" onclick="filterEvents(this,'除權息')">除權息</button>
          <button class="ev-chip" onclick="filterEvents(this,'總經')">總經</button>
          <button class="ev-chip" onclick="filterEvents(this,'升降息')">升降息</button>
          <button class="ev-chip" onclick="filterEvents(this,'法說會')">法說會</button>
        </div>
        <div class="ev-timeline" id="ev-timeline">
          <div class="ev-empty-msg" id="ev-empty-msg" style="display:none">近期無相關事件</div>
        </div>
      </div>
      <div class="ev-detail-panel" id="ev-detail-panel">
        <div class="ev-detail-empty">👈 點擊左側事件查看詳情</div>
      </div>
    </div>
  </div>
</section>

<script>window.DASHBOARD_DATA = {dashboard_data_json};</script>
<script src="/static/dashboard.js"></script>
</body>
</html>"""

    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ templates/index.html 已生成（v4 籌碼站四頁架構）")


if __name__ == '__main__':
    generate()
