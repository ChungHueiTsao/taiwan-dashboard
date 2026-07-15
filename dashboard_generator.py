import json
import os
import pandas as pd

def generate():
    try:
        with open('data/analysis.json', 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except:
        analysis = {"updated_at": "載入中", "market_sentiment": {"label": "🟡 中性", "color": "#eab308"},
                    "up_count": 0, "flat_count": 0, "down_count": 0, "top_sector": "-", "sectors": []}

    history_data = {}
    try:
        df = pd.read_csv('data/history.csv')
        for sector in df['sector'].unique():
            sd = df[df['sector'] == sector].tail(20)
            history_data[sector] = {"dates": sd['date'].tolist(), "scores": sd['score'].tolist()}
    except:
        pass

    sectors = analysis.get('sectors', [])
    updated_at = analysis.get('updated_at', '載入中')
    sentiment = analysis.get('market_sentiment', {"label": "🟡 中性", "color": "#eab308"})
    data_source = analysis.get('data_source', 'yfinance')
    delay_note = "盤中即時（延遲約5秒）" if data_source == 'realtime' else "資料延遲約15分鐘"

    try:
        with open('data/big_holders.json', 'r', encoding='utf-8') as f:
            big_holders = json.load(f)
    except Exception:
        big_holders = None

    def build_stock_js(sym, sd, sector_name, sector_emoji):
        """單一股票的完整前端資料物件，族群強弱/法人買超/大戶動向/量增排行 4個Tab共用同一份格式"""
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
        return {
            "name": sd.get('name', sym),
            "code": sym.replace('.TWO', '').replace('.TW', ''),
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
            "instSignal": inst_signal,
            "star": star,
            "up": c_color,
            "sectorName": sector_name,
            "sectorEmoji": sector_emoji,
            "foreignTrust5d": foreign_5d + trust_5d,
            "volumeRatioRaw": vr,
            "changePctRaw": c,
            "code_bare": sym.replace('.TWO', '').replace('.TW', '')
        }

    # 左側族群列表 + 蒐集全部個股（不限前5檔）供其他3個排行Tab與跳轉查詢使用
    sector_rows_html = ""
    all_stocks_flat = []   # [(sym, stock_js), ...]
    all_stocks_lookup = {}  # sym -> stock_js，供 JS 端 jumpToStock 查詢

    for i, s in enumerate(sectors):
        change = s['avg_change']
        color = "#ff4444" if change > 0 else "#22c55e"
        sign = "+" if change > 0 else ""
        score_pct = max(3, min(97, s['score']))
        is_up = "true" if change > 0 else "false"

        stock_items = list(s.get('stocks', {}).items())
        stock_items_sorted = sorted(stock_items, key=lambda x: x[1].get('change_pct', 0), reverse=True)

        stocks_js = []
        for sym, sd in stock_items_sorted:
            stock_js = build_stock_js(sym, sd, s['name'], s['emoji'])
            all_stocks_flat.append((sym, stock_js))
            all_stocks_lookup[sym] = stock_js
            if len(stocks_js) < 5:
                stocks_js.append(stock_js)

        summary = f"{s['name']}族群今日平均{sign}{change:.2f}%，{s['rating']}。領漲個股為{s['top_stock']}（{'+' if s['top_change']>0 else ''}{s['top_change']:.2f}%），籌碼面建議留意法人動向與量能變化。"

        sector_rows_html += f"""
        <div class="sector-row" onclick='selectSector(this,{json.dumps(s['name'])},{json.dumps(s['emoji'])},{json.dumps(s['rating'])},{json.dumps(summary)},{is_up},{json.dumps(stocks_js)})'>
          <span class="rank">{i+1}</span>
          <span class="name">{s['emoji']} {s['name']}</span>
          <span class="val" style="color:{color}">{sign}{change:.2f}%</span>
          <div class="bar-wrap"><div class="bar-bg"><div class="bar-fill" style="width:{score_pct}%;background:{color}"></div></div></div>
        </div>
        {"<hr class='divider'>" if i == sum(1 for x in sectors if x['avg_change']>0)-1 and i < len(sectors)-1 else ""}"""

    def rank_row_html(sym, label_html, sub, val_html, val2_html=""):
        return f"""
        <div class="rank-row" onclick="jumpToStock('{sym}')">
          <span class="rank-name">{label_html}</span>
          <span class="rank-sub">{sub}</span>
          <span class="rank-val">{val_html}</span>
          {f'<span class="rank-val2">{val2_html}</span>' if val2_html else ''}
        </div>"""

    # 法人買超 Tab：全部個股依 外資5日+投信5日 排序，前10買超、後3~5賣超
    foreign_sorted = sorted(all_stocks_flat, key=lambda x: x[1]['foreignTrust5d'], reverse=True)
    foreign_buy = [x for x in foreign_sorted if x[1]['foreignTrust5d'] > 0][:10]
    foreign_sell = [x for x in foreign_sorted if x[1]['foreignTrust5d'] < 0][-5:]
    foreign_rows_html = '<div class="rank-section-label">法人買超</div>'
    for sym, sj in foreign_buy:
        foreign_rows_html += rank_row_html(
            sym, f"{sj['star']}{sj['name']}", sj['sectorEmoji'] + sj['sectorName'],
            f"<span style='color:#ff4444'>{'+' if sj['foreignTrust5d']>=0 else ''}{sj['foreignTrust5d']:,}張</span>"
        )
    if foreign_sell:
        foreign_rows_html += '<div class="rank-section-label">法人賣超</div>'
        for sym, sj in reversed(foreign_sell):
            foreign_rows_html += rank_row_html(
                sym, f"{sj['star']}{sj['name']}", sj['sectorEmoji'] + sj['sectorName'],
                f"<span style='color:#22c55e'>{sj['foreignTrust5d']:,}張</span>"
            )
    if not foreign_buy and not foreign_sell:
        foreign_rows_html = '<div class="rank-empty">目前沒有法人買賣超資料</div>'

    # 大戶動向 Tab：讀 data/big_holders.json，依週變化排序；當週集保API無資料時顯示提示不崩潰
    holders_rows_html = ""
    if big_holders and big_holders.get('stocks'):
        holder_entries = []
        for sym, sj in all_stocks_flat:
            h = big_holders['stocks'].get(sj['code_bare'])
            if h:
                holder_entries.append((sym, sj, h))
        holder_entries.sort(key=lambda x: (x[2].get('ratio_change') if x[2].get('ratio_change') is not None else -999), reverse=True)
        for sym, sj, h in holder_entries:
            ratio = h.get('holder_ratio', 0)
            change = h.get('ratio_change')
            if change is None:
                change_html = "<span style='color:#8b949e'>首次收錄</span>"
            else:
                change_color = "#ff4444" if change >= 0 else "#22c55e"
                change_html = f"<span style='color:{change_color}'>{'+' if change>=0 else ''}{change:.2f}%</span>"
            holders_rows_html += rank_row_html(
                sym, sj['name'], sj['sectorEmoji'] + sj['sectorName'],
                f"{ratio:.2f}%", change_html
            )
        if not holder_entries:
            holders_rows_html = '<div class="rank-empty">本週尚無更新</div>'
    else:
        holders_rows_html = '<div class="rank-empty">本週尚無更新</div>'

    # 量增排行 Tab：全部個股依量比排序
    volume_sorted = sorted(all_stocks_flat, key=lambda x: x[1]['volumeRatioRaw'], reverse=True)
    volume_rows_html = ""
    for sym, sj in volume_sorted[:20]:
        c = sj['changePctRaw']
        c_color = "#ff4444" if c > 0 else "#22c55e"
        volume_rows_html += rank_row_html(
            sym, sj['name'], sj['sectorEmoji'] + sj['sectorName'],
            f"{sj['volumeRatioRaw']:.1f}x",
            f"<span style='color:{c_color}'>{'+' if c>0 else ''}{c:.2f}%</span>"
        )
    if not volume_sorted:
        volume_rows_html = '<div class="rank-empty">目前沒有量比資料</div>'

    all_stocks_json = json.dumps(all_stocks_lookup, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 事件頁面：除權息(自動) + 法說會/總經/升降息(手動維護清單)
    # ------------------------------------------------------------------
    try:
        with open('data/events.json', 'r', encoding='utf-8') as f:
            events = json.load(f)
    except Exception:
        events = []

    EVENT_TYPE_COLORS = {
        "除權息": "#58a6ff",
        "總經": "#a855f7",
        "升降息": "#f97316",
        "法說會": "#ec4899",
    }

    # bare code -> {name, sector, emoji}，用來把 related_stocks 展開成同族群個股
    code_to_info = {}
    sector_to_codes = {}
    for sym, sj in all_stocks_lookup.items():
        code_to_info[sj['code_bare']] = {"name": sj['name'], "sector": sj['sectorName'], "emoji": sj['sectorEmoji']}
        sector_to_codes.setdefault(sj['sectorName'], set()).add(sj['code_bare'])

    events_sorted = sorted(events, key=lambda e: e.get('date', ''))
    timeline_html = ""
    event_details = []
    for idx, e in enumerate(events_sorted):
        etype = e.get('type', '其他')
        color = EVENT_TYPE_COLORS.get(etype, '#8b949e')
        related = e.get('related_stocks', [])

        impact_stocks = []
        seen_codes = set()
        for code in related:
            info = code_to_info.get(code)
            if not info or code in seen_codes:
                continue
            seen_codes.add(code)
            impact_stocks.append({
                "code": code, "name": info['name'], "sector": info['emoji'] + info['sector'],
                "relation": "本尊", "impact": e.get('impact', '中'), "impactColor": "neutral"
            })
        related_sectors = {code_to_info[c]['sector'] for c in related if c in code_to_info}
        for sector_name in related_sectors:
            for code in sector_to_codes.get(sector_name, []):
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                info = code_to_info[code]
                impact_stocks.append({
                    "code": code, "name": info['name'], "sector": info['emoji'] + info['sector'],
                    "relation": "同族群", "impact": "同業關注", "impactColor": "neutral"
                })

        event_details.append({
            "date": e.get('date', ''), "type": etype, "title": e.get('title', ''),
            "summary": e.get('title', ''), "impactStocks": impact_stocks
        })

        timeline_html += f"""
        <div class="ev-card" data-type="{etype}" onclick="showEventDetail({idx})">
          <div class="ev-card-date">{e.get('date','')}</div>
          <div class="ev-card-title">{e.get('title','')}</div>
          <span class="ev-type-tag" style="background:{color}22;color:{color};border:1px solid {color}44">{etype}</span>
        </div>"""

    if not timeline_html:
        timeline_html = '<div class="rank-empty">近期沒有收錄到事件</div>'

    events_json = json.dumps(event_details, ensure_ascii=False)

    # Plotly 歷史折線圖
    line_traces = ""
    max_hist_len = 1
    colors = ["#58a6ff","#ff4444","#22c55e","#eab308","#a855f7","#f97316","#06b6d4","#ec4899","#84cc16","#f43f5e","#8b5cf6","#14b8a6","#fb923c"]
    for i, s in enumerate(sectors[:13]):
        name = s['name']
        if name in history_data:
            hd = history_data[name]
            max_hist_len = max(max_hist_len, len(hd['dates']))
            color = colors[i % len(colors)]
            line_traces += f"""{{x:{json.dumps(hd['dates'])},y:{json.dumps(hd['scores'])},name:'{name}',type:'scatter',mode:'lines+markers',line:{{color:'{color}',width:1.5}},marker:{{color:'{color}',size:5}}}},"""

    os.makedirs('templates', exist_ok=True)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🇹🇼 台股族群每日監控</title>
<script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#e6edf3;font-family:system-ui,-apple-system,sans-serif;font-size:13px;overflow-x:hidden}}
.nav{{background:#161b22;border-bottom:1px solid #30363d;padding:8px 14px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
.nav h1{{font-size:14px;font-weight:600}}
.nav-left{{display:flex;align-items:center;gap:14px}}
.nav-tabs{{display:flex;gap:4px}}
.nav-tab{{padding:4px 12px;border-radius:5px;font-size:11px;cursor:pointer;border:1px solid transparent;background:transparent;color:#8b949e}}
.nav-tab:hover{{background:#21262d}}
.nav-tab.active{{background:#58a6ff22;border-color:#58a6ff66;color:#58a6ff}}
.nav .meta{{display:flex;align-items:center;gap:8px;font-size:11px;color:#8b949e}}
.badge{{padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600}}
.btn-sm{{background:#21262d;border:1px solid #30363d;color:#8b949e;padding:3px 10px;border-radius:4px;font-size:11px;cursor:pointer}}
.btn-sm:hover{{background:#30363d;color:#e6edf3}}
.main{{display:grid;grid-template-columns:240px 1fr;height:calc(100vh - 38px);overflow:hidden}}
/* 事件頁面 */
.events-page{{height:calc(100vh - 38px);overflow:hidden}}
.ev-wrap{{display:grid;grid-template-columns:320px 1fr;height:100%}}
.ev-timeline-panel{{border-right:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}}
.ev-filter-chips{{display:flex;gap:4px;flex-wrap:wrap;padding:10px;border-bottom:1px solid #21262d;flex-shrink:0}}
.ev-chip{{padding:3px 9px;border-radius:12px;font-size:10px;cursor:pointer;border:1px solid #30363d;background:#21262d;color:#8b949e}}
.ev-chip.active{{background:#58a6ff22;border-color:#58a6ff66;color:#58a6ff}}
.ev-timeline{{flex:1;overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:8px}}
.ev-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:9px 10px;cursor:pointer;transition:border-color .15s}}
.ev-card:hover{{border-color:#58a6ff66}}
.ev-card.active{{border-color:#58a6ff;background:#161b22}}
.ev-card-date{{font-size:9px;color:#8b949e;margin-bottom:4px}}
.ev-card-title{{font-size:12px;font-weight:500;margin-bottom:6px;line-height:1.4}}
.ev-type-tag{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:9px;font-weight:600}}
.ev-detail-panel{{padding:20px;overflow-y:auto}}
.ev-detail-empty{{color:#8b949e;font-size:13px;text-align:center;padding-top:60px}}
.ev-empty-msg{{color:#8b949e;font-size:13px;text-align:center;padding-top:60px}}
.ev-detail-title{{font-size:18px;font-weight:700;margin-bottom:6px}}
.ev-detail-meta{{display:flex;align-items:center;gap:8px;margin-bottom:16px}}
.ev-detail-date{{font-size:11px;color:#8b949e}}
.ev-detail-summary{{font-size:12px;color:#8b949e;line-height:1.6;padding:10px 12px;background:#161b22;border-radius:8px;border-left:3px solid #58a6ff;margin-bottom:20px}}
.impact-table-title{{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}}
.impact-table{{width:100%;border-collapse:collapse;font-size:12px}}
.impact-table th{{text-align:left;padding:7px 10px;color:#8b949e;font-weight:500;font-size:10px;border-bottom:1px solid #30363d}}
.impact-table td{{padding:7px 10px;border-bottom:1px solid #21262d}}
.impact-table tr:hover td{{background:#161b22}}
.impact-relation{{font-size:10px;padding:2px 7px;border-radius:4px;background:#21262d;color:#8b949e}}
.impact-relation.self{{background:#58a6ff22;color:#58a6ff}}
/* LEFT */
.left{{border-right:1px solid #30363d;padding:8px 6px;display:flex;flex-direction:column;gap:2px;overflow-y:auto}}
.left-title{{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;padding:0 4px;margin-bottom:4px;flex-shrink:0}}
.rank-tabs{{display:flex;gap:3px;padding:0 2px;margin-bottom:6px;flex-shrink:0;flex-wrap:wrap}}
.rank-tab{{padding:3px 7px;border-radius:4px;font-size:10px;cursor:pointer;border:1px solid #30363d;background:#21262d;color:#8b949e;white-space:nowrap}}
.rank-tab.active{{background:#58a6ff22;border-color:#58a6ff66;color:#58a6ff}}
.rank-list{{display:none;flex-direction:column;gap:2px}}
.rank-list.active{{display:flex}}
.rank-section-label{{font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;padding:6px 4px 2px;flex-shrink:0}}
.rank-row{{display:flex;align-items:center;gap:4px;padding:5px 6px;border-radius:6px;cursor:pointer;transition:background .15s;flex-shrink:0}}
.rank-row:hover{{background:#161b22}}
.rank-name{{font-size:11px;font-weight:500;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}}
.rank-sub{{font-size:9px;color:#8b949e;flex-shrink:0;white-space:nowrap;max-width:56px;overflow:hidden;text-overflow:ellipsis}}
.rank-val{{font-size:10px;font-weight:700;flex-shrink:0;text-align:right;white-space:nowrap}}
.rank-val2{{font-size:9px;flex-shrink:0;text-align:right;white-space:nowrap;width:44px}}
.rank-empty{{font-size:11px;color:#8b949e;text-align:center;padding:20px 8px}}
.sector-row{{display:flex;align-items:center;gap:5px;padding:5px 6px;border-radius:6px;cursor:pointer;transition:all .15s;border:1px solid transparent;flex-shrink:0}}
.sector-row:hover{{background:#161b22}}
.sector-row.active{{background:#161b22;border-color:#58a6ff55}}
.sector-row .rank{{font-size:10px;color:#8b949e;width:14px;text-align:right;flex-shrink:0}}
.sector-row .name{{font-size:11px;font-weight:500;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sector-row .val{{font-size:11px;font-weight:700;width:50px;text-align:right;flex-shrink:0}}
.sector-row .bar-wrap{{width:30px;flex-shrink:0}}
.bar-bg{{background:#21262d;border-radius:2px;height:3px}}
.bar-fill{{height:100%;border-radius:2px}}
.divider{{border:none;border-top:1px solid #21262d;margin:3px 0;flex-shrink:0}}
/* RIGHT */
.right{{display:flex;flex-direction:column;overflow:hidden}}
/* HEADER 區 */
.right-header{{padding:8px 14px 6px;border-bottom:1px solid #21262d;flex-shrink:0}}
.idx-tabs{{display:flex;align-items:center;gap:6px;margin-bottom:6px}}
.idx-btn{{padding:3px 10px;border-radius:4px;font-size:11px;cursor:pointer;border:1px solid #30363d;background:#21262d;color:#8b949e}}
.idx-btn.active{{background:#58a6ff22;border-color:#58a6ff66;color:#58a6ff}}
.idx-val{{display:flex;align-items:baseline;gap:8px}}
.big{{font-size:20px;font-weight:700}}
.ohlc{{display:flex;gap:10px;font-size:10px;color:#8b949e;margin-top:2px}}
/* 族群模式 header */
.sector-header{{display:none}}
.s-back{{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}}
.s-title-row{{display:flex;align-items:baseline;gap:8px;margin-bottom:4px}}
.s-summary{{font-size:11px;color:#8b949e;line-height:1.5;padding:5px 8px;background:#0d1117;border-radius:6px;border-left:2px solid #58a6ff;margin-bottom:6px}}
.stock-tabs{{display:flex;gap:4px;overflow-x:auto;padding-bottom:2px}}
.stock-tabs::-webkit-scrollbar{{height:3px}}
.stock-tabs::-webkit-scrollbar-track{{background:#21262d}}
.stock-tabs::-webkit-scrollbar-thumb{{background:#30363d;border-radius:2px}}
.stock-tab{{padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;border:1px solid #30363d;background:#21262d;color:#8b949e;white-space:nowrap;flex-shrink:0}}
.stock-tab.active-up{{background:#ff444422;border-color:#ff444466;color:#ff4444}}
.stock-tab.active-down{{background:#22c55e22;border-color:#22c55e66;color:#22c55e}}
/* 個股資訊面板 */
.stock-info-panel{{display:none;padding:6px 14px;border-bottom:1px solid #21262d;flex-shrink:0}}
.info-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-bottom:6px}}
.info-card{{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:5px 8px;text-align:center}}
.ic-label{{font-size:9px;color:#8b949e}}
.ic-val{{font-size:12px;font-weight:600;margin-top:1px}}
.suggest-box{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;background:#0d1117;border:1px solid #30363d;border-radius:6px;overflow:hidden}}
.suggest-item{{padding:6px 8px;text-align:center;border-right:1px solid #21262d}}
.suggest-item:last-child{{border-right:none}}
.sl{{font-size:9px;color:#8b949e;margin-bottom:2px}}
.sv{{font-size:13px;font-weight:700}}
.st{{font-size:9px;color:#8b949e;margin-top:1px}}
/* 週期按鈕 */
.period-row{{padding:4px 14px;display:flex;align-items:center;gap:3px;border-bottom:1px solid #21262d;flex-shrink:0}}
.period-btn{{padding:2px 6px;border-radius:3px;font-size:10px;cursor:pointer;border:none;background:transparent;color:#8b949e}}
.period-btn.active{{background:#58a6ff22;color:#58a6ff}}
.ind-row{{display:flex;gap:6px;font-size:9px;color:#8b949e;margin-left:auto;flex-wrap:wrap}}
.dot{{width:8px;height:3px;border-radius:2px;display:inline-block;vertical-align:middle;margin-right:2px}}
/* 圖表區 */
.chart-main{{flex:1;padding:4px 14px 0;min-height:0;display:flex;flex-direction:column}}
.kline-info-bar{{display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#8b949e;padding:2px 0 4px;flex-shrink:0}}
.kline-info-bar b{{color:#e6edf3;font-weight:600}}
#mainChart .hoverlayer .hovertext{{display:none}}
/* 歷史趨勢區（大盤模式） */
.history-chart{{padding:4px 14px;flex:1;min-height:0;display:none}}
/* 底部快覽 */
.idx-footer{{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #30363d;flex-shrink:0}}
.idx-footer-card{{padding:6px 10px;text-align:center;border-right:1px solid #21262d}}
.idx-footer-card:last-child{{border-right:none}}
.f-name{{font-size:9px;color:#8b949e}}
.f-val{{font-size:12px;font-weight:600}}
.f-chg{{font-size:9px}}
/* Scrollbar */
.left::-webkit-scrollbar{{width:3px}}
.left::-webkit-scrollbar-track{{background:transparent}}
.left::-webkit-scrollbar-thumb{{background:#30363d;border-radius:2px}}
</style>
</head>
<body>

<div class="nav">
  <div class="nav-left">
    <h1>🇹🇼 台股族群每日監控</h1>
    <div class="nav-tabs">
      <button class="nav-tab active" id="nav-tab-monitor" onclick="showPage('monitor')">📊 監控</button>
      <button class="nav-tab" id="nav-tab-events" onclick="showPage('events')">📅 事件</button>
    </div>
  </div>
  <div class="meta">
    <span>最後更新：{updated_at}</span>
    <span style="font-size:9px;color:#8b949e">（{delay_note}）</span>
    <span class="badge" style="background:{sentiment['color']}22;color:{sentiment['color']};border:1px solid {sentiment['color']}44">{sentiment['label']}</span>
    <button class="btn-sm" onclick="location.href='/api/refresh?redirect=1'">🔄 立即更新</button>
  </div>
</div>

<div class="main" id="page-monitor">
  <!-- ===== LEFT ===== -->
  <div class="left">
    <div class="rank-tabs">
      <button class="rank-tab active" onclick="switchRank(this,'sector')">族群強弱</button>
      <button class="rank-tab" onclick="switchRank(this,'foreign')">法人買超</button>
      <button class="rank-tab" onclick="switchRank(this,'holders')">大戶動向</button>
      <button class="rank-tab" onclick="switchRank(this,'volume')">量增排行</button>
    </div>
    <div class="rank-list active" id="rank-sector">{sector_rows_html}</div>
    <div class="rank-list" id="rank-foreign">{foreign_rows_html}</div>
    <div class="rank-list" id="rank-holders">{holders_rows_html}</div>
    <div class="rank-list" id="rank-volume">{volume_rows_html}</div>
  </div>

  <!-- ===== RIGHT ===== -->
  <div class="right">

    <!-- 大盤模式 Header -->
    <div class="right-header" id="market-header">
      <div class="idx-tabs">
        <button class="idx-btn active" onclick="switchIndex(this,'TWII','加權指數')">加權指數</button>
        <button class="idx-btn" onclick="switchIndex(this,'TWOII','OTC 櫃買')">OTC 櫃買</button>
        <button class="idx-btn" onclick="switchIndex(this,'TAIFEX','台指期')">台指期</button>
      </div>
      <div class="idx-val">
        <span class="big" id="idx-price">-</span>
        <span id="idx-chg" style="font-size:12px;font-weight:600;color:#8b949e">載入中...</span>
        <span style="font-size:10px;color:#8b949e">{updated_at}</span>
      </div>
      <div class="ohlc" id="idx-ohlc">
        <span>開 -</span><span>高 -</span><span>低 -</span><span>量 -</span>
      </div>
    </div>

    <!-- 族群模式 Header -->
    <div class="right-header sector-header" id="sector-header">
      <div class="s-back">
        <button class="btn-sm" onclick="backToMarket()">← 返回大盤</button>
        <span id="s-rating" style="font-size:10px;font-weight:600"></span>
      </div>
      <div class="s-title-row">
        <span id="s-title" style="font-size:15px;font-weight:700"></span>
        <span id="s-avg" style="font-size:13px;font-weight:700"></span>
      </div>
      <div class="s-summary" id="s-summary"></div>
      <div class="stock-tabs" id="stock-tabs"></div>
    </div>

    <!-- 個股資訊面板 -->
    <div class="stock-info-panel" id="stock-info-panel">
      <div class="info-grid">
        <div class="info-card"><div class="ic-label">現價</div><div class="ic-val" id="s-price">-</div></div>
        <div class="info-card"><div class="ic-label">漲跌幅</div><div class="ic-val" id="s-chg">-</div></div>
        <div class="info-card"><div class="ic-label">成交量</div><div class="ic-val" id="s-vol">-</div></div>
        <div class="info-card"><div class="ic-label">量比</div><div class="ic-val" id="s-vr">-</div></div>
        <div class="info-card"><div class="ic-label">外資5日</div><div class="ic-val" id="s-foreign">-</div></div>
        <div class="info-card"><div class="ic-label">投信5日</div><div class="ic-val" id="s-trust">-</div></div>
      </div>
      <div class="suggest-box">
        <div class="suggest-item">
          <div class="sl">📌 建議進場</div>
          <div class="sv" style="color:#ff4444" id="s-entry">-</div>
          <div class="st" id="s-entry-note">-</div>
        </div>
        <div class="suggest-item">
          <div class="sl">🛑 停損價位</div>
          <div class="sv" style="color:#22c55e" id="s-stop">-</div>
          <div class="st" id="s-stop-note">-</div>
        </div>
        <div class="suggest-item">
          <div class="sl">🎯 目標價位</div>
          <div class="sv" style="color:#58a6ff" id="s-target">-</div>
          <div class="st" id="s-target-note">-</div>
        </div>
        <div class="suggest-item">
          <div class="sl">💡 操作建議</div>
          <div class="sv" style="font-size:11px;color:#eab308" id="s-action">-</div>
          <div class="st" id="s-action-note">-</div>
        </div>
      </div>
    </div>

    <!-- 週期按鈕 -->
    <div class="period-row">
      <button class="period-btn active" onclick="setPeriod(this)">日</button>
      <button class="period-btn" onclick="setPeriod(this)">週</button>
      <button class="period-btn" onclick="setPeriod(this)">月</button>
      <div style="width:1px;height:14px;background:#30363d;margin:0 4px"></div>
      <div class="ind-row">
        <span><span class="dot" style="background:#f97316"></span>MA5</span>
        <span><span class="dot" style="background:#58a6ff"></span>MA20</span>
        <span><span class="dot" style="background:#a855f7"></span>MA60</span>
        <span><span class="dot" style="background:#8b949e;opacity:.5"></span>布林帶</span>
      </div>
      <button class="btn-sm" id="history-toggle-btn" onclick="toggleHistoryView()" style="margin-left:8px">📈 族群趨勢</button>
    </div>

    <!-- K線＋KD＋成交量 合併子圖（共用X軸，十字線貫穿） -->
    <div class="chart-main" id="chart-main">
      <div class="kline-info-bar" id="kline-info-bar">
        <span id="ki-date">-</span>
        <span>開 <b id="ki-open">-</b></span>
        <span>高 <b id="ki-high">-</b></span>
        <span>低 <b id="ki-low">-</b></span>
        <span>收 <b id="ki-close">-</b></span>
        <span style="color:#f97316">MA5 <b id="ki-ma5">-</b></span>
        <span style="color:#58a6ff">MA20 <b id="ki-ma20">-</b></span>
        <span style="color:#a855f7">MA60 <b id="ki-ma60">-</b></span>
        <span style="color:#8b949e">布林上 <b id="ki-bollu">-</b></span>
        <span style="color:#8b949e">布林下 <b id="ki-bolld">-</b></span>
        <span style="color:#f97316">K <b id="ki-k">-</b></span>
        <span style="color:#58a6ff">D <b id="ki-d">-</b></span>
        <span>量 <b id="ki-vol">-</b></span>
      </div>
      <div id="mainChart" style="width:100%;flex:1;min-height:0"></div>
    </div>

    <!-- 歷史趨勢（大盤模式） -->
    <div class="history-chart" id="history-chart">
      <div id="historyChart" style="width:100%;height:100%"></div>
    </div>

    <!-- 底部快覽 -->
    <div class="idx-footer">
      <div class="idx-footer-card" style="border-top:2px solid #58a6ff">
        <div class="f-name">加權指數</div>
        <div class="f-val" id="f-twii-val">-</div>
        <div class="f-chg" id="f-twii-chg">-</div>
      </div>
      <div class="idx-footer-card">
        <div class="f-name">OTC 櫃買</div>
        <div class="f-val" id="f-twoii-val">-</div>
        <div class="f-chg" id="f-twoii-chg">-</div>
      </div>
      <div class="idx-footer-card">
        <div class="f-name">台指期</div>
        <div class="f-val" id="f-fut-val">-</div>
        <div class="f-chg" id="f-fut-chg">-</div>
      </div>
    </div>
  </div>
</div>

<!-- ===== 事件頁面 ===== -->
<div class="events-page" id="page-events" style="display:none">
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
        {timeline_html}
        <div class="ev-empty-msg" id="ev-empty-msg" style="display:none">近期無相關事件</div>
      </div>
    </div>
    <div class="ev-detail-panel" id="ev-detail-panel">
      <div class="ev-detail-empty">👈 點擊左側事件查看詳情</div>
    </div>
  </div>
</div>

<script>
const ALL_STOCKS = {all_stocks_json};
const EVENTS = {events_json};
const PLOT_CONFIG = {{responsive:true,displayModeBar:false,scrollZoom:true}};
const DARK_LAYOUT = {{
  paper_bgcolor:'#0d1117',plot_bgcolor:'#0d1117',
  font:{{color:'#8b949e',size:10}},
  margin:{{l:40,r:8,t:4,b:20}},
  xaxis:{{gridcolor:'#21262d',showgrid:true,zeroline:false}},
  yaxis:{{gridcolor:'#21262d',showgrid:true,zeroline:false,side:'right'}}
}};

// ---- 真實K線資料（透過 /api/kline/<symbol> 取得，取代模擬資料）----
const klineCache = {{}};
async function fetchKline(symbol) {{
  if(klineCache[symbol]) return klineCache[symbol];
  try {{
    const res = await fetch('/api/kline/' + encodeURIComponent(symbol));
    if(!res.ok) return null;
    const data = await res.json();
    if(!data.dates || data.dates.length === 0) return null;
    const result = {{
      dates: data.dates, o: data.open, h: data.high, l: data.low, c: data.close, v: data.volume,
      colors: data.close.map((c,i)=> c >= data.open[i] ? '#ff4444' : '#22c55e')
    }};
    klineCache[symbol] = result;
    return result;
  }} catch(e) {{
    console.error('K線資料取得失敗', symbol, e);
    return null;
  }}
}}
const EMPTY_KLINE = {{dates:[],o:[],h:[],l:[],c:[],v:[],colors:[]}};

function calcMA(data, n) {{
  return data.map((v,i,a)=>i<n-1?null:a.slice(i-n+1,i+1).reduce((s,x)=>s+x,0)/n);
}}

function calcBoll(c, n=20, k=2) {{
  const mid=calcMA(c,n);
  const upper=[],lower=[];
  for(let i=0;i<c.length;i++) {{
    if(i<n-1){{upper.push(null);lower.push(null);continue;}}
    const slice=c.slice(i-n+1,i+1);
    const mean=mid[i];
    const std=Math.sqrt(slice.reduce((s,x)=>s+(x-mean)**2,0)/n);
    upper.push(+(mean+k*std).toFixed(1));
    lower.push(+(mean-k*std).toFixed(1));
  }}
  return {{mid,upper,lower}};
}}

function calcKD(h,l,c,n=9) {{
  const K=[],D=[];
  let k=50,d=50;
  for(let i=0;i<c.length;i++) {{
    const sliceH=h.slice(Math.max(0,i-n+1),i+1);
    const sliceL=l.slice(Math.max(0,i-n+1),i+1);
    const hn=Math.max(...sliceH),ln=Math.min(...sliceL);
    const rsv=hn===ln?50:(c[i]-ln)/(hn-ln)*100;
    k=k*2/3+rsv/3; d=d*2/3+k/3;
    K.push(+k.toFixed(1)); D.push(+d.toFixed(1));
  }}
  return {{K,D}};
}}

let baseKData = EMPTY_KLINE;
let currentPeriod = '日';
let currentIndexKData = null;

function aggregateData(base, period) {{
  if(period==='日'||!base.dates||base.dates.length===0) return base;
  const groupKey = (dateStr) => {{
    if(period==='週') {{
      const dt=new Date(dateStr);
      const day=dt.getDay()||7;
      dt.setDate(dt.getDate()-day+1);
      return dt.toISOString().split('T')[0];
    }}
    return dateStr.slice(0,7);
  }};
  const groups={{}}; const order=[];
  for(let i=0;i<base.dates.length;i++) {{
    const key=groupKey(base.dates[i]);
    if(!groups[key]) {{
      groups[key]={{o:base.o[i],h:base.h[i],l:base.l[i],c:base.c[i],v:base.v[i],firstDate:base.dates[i]}};
      order.push(key);
    }} else {{
      const g=groups[key];
      g.h=Math.max(g.h,base.h[i]);
      g.l=Math.min(g.l,base.l[i]);
      g.c=base.c[i];
      g.v+=base.v[i];
    }}
  }}
  const dates=[],o=[],h=[],l=[],c=[],v=[],colors=[];
  order.forEach(key=>{{
    const g=groups[key];
    dates.push(g.firstDate); o.push(g.o); h.push(g.h); l.push(g.l); c.push(g.c); v.push(g.v);
    colors.push(g.c>=g.o?'#ff4444':'#22c55e');
  }});
  return {{dates,o,h,l,c,v,colors}};
}}

let _klineInfo = null;
function showKlineInfoAt(idx) {{
  const info = _klineInfo;
  if(!info || idx==null || idx<0 || idx>=info.dates.length) return;
  const fmt = v => (v===null||v===undefined||isNaN(v)) ? '-' : (+v).toFixed(2);
  document.getElementById('ki-date').textContent=info.dates[idx];
  document.getElementById('ki-open').textContent=fmt(info.o[idx]);
  document.getElementById('ki-high').textContent=fmt(info.h[idx]);
  document.getElementById('ki-low').textContent=fmt(info.l[idx]);
  document.getElementById('ki-close').textContent=fmt(info.c[idx]);
  document.getElementById('ki-ma5').textContent=fmt(info.ma5[idx]);
  document.getElementById('ki-ma20').textContent=fmt(info.ma20[idx]);
  document.getElementById('ki-ma60').textContent=fmt(info.ma60[idx]);
  document.getElementById('ki-bollu').textContent=fmt(info.bollU[idx]);
  document.getElementById('ki-bolld').textContent=fmt(info.bollL[idx]);
  document.getElementById('ki-k').textContent=fmt(info.kdK[idx]);
  document.getElementById('ki-d').textContent=fmt(info.kdD[idx]);
  document.getElementById('ki-vol').textContent=(info.v[idx]/100000000).toFixed(2)+'億';
}}

// K線＋KD＋成交量 合併成單一 Plotly Figure 的三列子圖，共用X軸，十字線貫穿
function renderKline() {{
  const d=aggregateData(baseKData,currentPeriod);
  if(!d.dates||d.dates.length===0) return;
  const boll=calcBoll(d.c); const kd=calcKD(d.h,d.l,d.c);
  const ma5=calcMA(d.c,5),ma20=calcMA(d.c,20),ma60=calcMA(d.c,60);
  _klineInfo = {{dates:d.dates,o:d.o,h:d.h,l:d.l,c:d.c,v:d.v,ma5,ma20,ma60,bollU:boll.upper,bollL:boll.lower,kdK:kd.K,kdD:kd.D}};

  const maxIdx = d.dates.length-1;
  const tickvals = d.dates.filter((_,i)=>i%10===0);
  const ticktext = tickvals.map(x=>x.slice(5));
  const spike = {{showspikes:true,spikemode:'across',spikesnap:'cursor',spikecolor:'#58a6ff',spikethickness:1,spikedash:'dash'}};

  const hasVolume = d.v.some(v => v > 0);

  const traces = [
    {{type:'candlestick',x:d.dates,open:d.o,high:d.h,low:d.l,close:d.c,xaxis:'x',yaxis:'y',
      increasing:{{line:{{color:'#ff4444'}},fillcolor:'#ff4444'}},
      decreasing:{{line:{{color:'#22c55e'}},fillcolor:'#22c55e'}},name:'K線'}},
    {{x:d.dates,y:ma5,type:'scatter',mode:'lines',line:{{color:'#f97316',width:1}},name:'MA5',xaxis:'x',yaxis:'y'}},
    {{x:d.dates,y:ma20,type:'scatter',mode:'lines',line:{{color:'#58a6ff',width:1}},name:'MA20',xaxis:'x',yaxis:'y'}},
    {{x:d.dates,y:ma60,type:'scatter',mode:'lines',line:{{color:'#a855f7',width:1}},name:'MA60',xaxis:'x',yaxis:'y'}},
    {{x:d.dates,y:boll.upper,type:'scatter',mode:'lines',line:{{color:'#8b949e',width:0.8,dash:'dot'}},name:'布林上',showlegend:false,xaxis:'x',yaxis:'y'}},
    {{x:d.dates,y:boll.lower,type:'scatter',mode:'lines',line:{{color:'#8b949e',width:0.8,dash:'dot'}},name:'布林下',
      fill:'tonexty',fillcolor:'rgba(139,148,158,0.04)',showlegend:false,xaxis:'x',yaxis:'y'}},
    {{x:d.dates,y:kd.K,type:'scatter',mode:'lines',line:{{color:'#f97316',width:1.2}},name:'K',xaxis:'x',yaxis:'y2'}},
    {{x:d.dates,y:kd.D,type:'scatter',mode:'lines',line:{{color:'#58a6ff',width:1.2}},name:'D',xaxis:'x',yaxis:'y2'}},
    {{x:[d.dates[0],d.dates[maxIdx]],y:[80,80],type:'scatter',mode:'lines',
      line:{{color:'#30363d',width:0.8,dash:'dot'}},showlegend:false,hoverinfo:'skip',xaxis:'x',yaxis:'y2'}},
    {{x:[d.dates[0],d.dates[maxIdx]],y:[20,20],type:'scatter',mode:'lines',
      line:{{color:'#30363d',width:0.8,dash:'dot'}},showlegend:false,hoverinfo:'skip',xaxis:'x',yaxis:'y2'}},
  ];
  if(hasVolume) {{
    traces.push({{x:d.dates,y:d.v,type:'bar',marker:{{color:d.colors,opacity:0.8}},name:'成交量',xaxis:'x',yaxis:'y3'}});
  }}

  const annotations = hasVolume ? [] : [{{
    text:'指數無成交量資料', xref:'paper', yref:'paper', x:0.5, y:0.075,
    showarrow:false, font:{{color:'#8b949e',size:10}}
  }}];

  Plotly.newPlot('mainChart', traces, {{
    paper_bgcolor:'#0d1117',plot_bgcolor:'#0d1117',
    font:{{color:'#8b949e',size:10}},
    margin:{{l:50,r:8,t:4,b:20}},
    showlegend:false,
    dragmode:'pan',
    hovermode:'x unified',
    annotations,
    xaxis:{{gridcolor:'#21262d',showgrid:true,zeroline:false,rangeslider:{{visible:false}},type:'category',
      range:[0,maxIdx],tickmode:'array',tickvals,ticktext,...spike}},
    yaxis:{{gridcolor:'#21262d',showgrid:true,zeroline:false,side:'right',fixedrange:true,
      domain:[0.35,1.0],showspikes:true}},
    yaxis2:{{gridcolor:'#21262d',showgrid:true,zeroline:false,side:'right',fixedrange:true,
      domain:[0.18,0.32],range:[0,100],dtick:40,showspikes:true}},
    yaxis3:{{gridcolor:'#21262d',showgrid:true,zeroline:false,side:'right',fixedrange:true,
      domain:[0,0.15],showticklabels:false,showspikes:true}}
  }}, PLOT_CONFIG);

  attachZoomBound('mainChart', maxIdx);
  attachShiftWheelPan('mainChart');
  attachMainHover('mainChart');
  showKlineInfoAt(maxIdx);
}}

// 縮放/平移時，限制在資料範圍內
function attachZoomBound(divId, maxIdx) {{
  const div = document.getElementById(divId);
  let syncing = false;
  div.removeAllListeners && div.removeAllListeners('plotly_relayout');
  div.on('plotly_relayout', (ev) => {{
    if(syncing) return;
    let x0 = ev['xaxis.range[0]'], x1 = ev['xaxis.range[1]'];
    if(x0 === undefined && ev['xaxis.range']) {{ x0 = ev['xaxis.range'][0]; x1 = ev['xaxis.range'][1]; }}
    if(x0 === undefined || x1 === undefined) return;

    let nx0 = x0, nx1 = x1;
    const width = nx1 - nx0;
    if(width >= maxIdx) {{
      nx0 = 0; nx1 = maxIdx;
    }} else {{
      if(nx0 < 0) {{ nx1 -= nx0; nx0 = 0; }}
      if(nx1 > maxIdx) {{ nx0 -= (nx1 - maxIdx); nx1 = maxIdx; }}
      if(nx0 < 0) nx0 = 0;
    }}
    if(Math.abs(nx0 - x0) > 1e-6 || Math.abs(nx1 - x1) > 1e-6) {{
      syncing = true;
      Plotly.relayout(div, {{'xaxis.range':[nx0,nx1]}});
      syncing = false;
    }}
  }});
}}

// Shift+滾輪：縮放後可左右平移查看
function attachShiftWheelPan(divId) {{
  const div = document.getElementById(divId);
  if(div._shiftPanBound) return;
  div._shiftPanBound = true;
  div.addEventListener('wheel', function(ev) {{
    if(!ev.shiftKey) return;
    ev.preventDefault();
    ev.stopPropagation();
    const layout = div.layout;
    if(!layout || !layout.xaxis || !layout.xaxis.range) return;
    const [x0,x1] = layout.xaxis.range;
    const span = x1 - x0;
    const shift = span * 0.15 * (ev.deltaY > 0 ? 1 : -1);
    Plotly.relayout(div, {{'xaxis.range':[x0+shift, x1+shift]}});
  }}, {{passive:false}});
}}

// hover 時把該日期的所有數值同步更新到頂部資訊列（單一圖表，三子圖天生共用X軸與十字線）
function attachMainHover(divId) {{
  const div = document.getElementById(divId);
  if(div._hoverBound) return;
  div._hoverBound = true;
  div.on('plotly_hover', (ev) => {{
    if(!ev.points || !ev.points.length) return;
    const p=ev.points[0];
    const idx=(p.pointIndex!==undefined)?p.pointIndex:p.pointNumber;
    showKlineInfoAt(idx);
  }});
  div.on('plotly_unhover', () => {{
    if(_klineInfo) showKlineInfoAt(_klineInfo.dates.length-1);
  }});
}}

// 歷史趨勢圖
const HISTORY_MAX_IDX = {max_hist_len - 1};
function renderHistory() {{
  const traces=[{line_traces}];
  if(traces.length===0) return;
  Plotly.newPlot('historyChart',traces,{{
    ...DARK_LAYOUT,
    margin:{{l:40,r:8,t:4,b:30}},
    showlegend:true,
    dragmode:'pan',
    hovermode:'x',
    legend:{{bgcolor:'#161b22',bordercolor:'#30363d',borderwidth:1,font:{{size:9}}}},
    xaxis:{{...DARK_LAYOUT.xaxis,type:'category',range:[0,HISTORY_MAX_IDX]}},
    yaxis:{{...DARK_LAYOUT.yaxis,title:'強勢評分',fixedrange:true}}
  }},PLOT_CONFIG);
  attachZoomBound('historyChart',HISTORY_MAX_IDX);
  attachShiftWheelPan('historyChart');
}}

// ---- 互動控制 ----
function fmtIdxNum(n) {{ return n.toLocaleString('zh-TW',{{maximumFractionDigits:2}}); }}

function updateIndexHeader(kline) {{
  const n=kline.c.length;
  const price=kline.c[n-1];
  const prev=n>1?kline.c[n-2]:price;
  const chg=prev?((price-prev)/prev*100):0;
  const diff=price-prev;
  const up=chg>=0;
  const color=up?'#ff4444':'#22c55e';
  const arrow=up?'▲':'▼';
  document.getElementById('idx-price').textContent=fmtIdxNum(price);
  const chgEl=document.getElementById('idx-chg');
  chgEl.textContent=`${{arrow}} ${{fmtIdxNum(Math.abs(diff))}} (${{chg.toFixed(2)}}%)`;
  chgEl.style.color=color;
  document.getElementById('idx-ohlc').innerHTML=
    `<span>開 ${{fmtIdxNum(kline.o[n-1])}}</span><span>高 ${{fmtIdxNum(kline.h[n-1])}}</span><span>低 ${{fmtIdxNum(kline.l[n-1])}}</span><span>量 ${{kline.v[n-1].toLocaleString()}}</span>`;
  return {{price,chg,color,arrow}};
}}

async function switchIndex(btn, symbol, label) {{
  document.querySelectorAll('.idx-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const kline=await fetchKline(symbol);
  if(!kline) return;
  baseKData=kline;
  currentIndexKData=kline;
  updateIndexHeader(kline);
  if(_showingHistory) resetHistoryToggle();
  document.getElementById('chart-main').style.display='flex';
  document.getElementById('chart-main').style.flexDirection='column';
  document.getElementById('history-chart').style.display='none';
  renderKline();
}}

function setPeriod(btn) {{
  document.querySelectorAll('.period-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  currentPeriod=btn.textContent;
  renderKline();
}}

// 左側排行 Tab 切換：族群強弱／法人買超／大戶動向／量增排行
function switchRank(btn, tab) {{
  document.querySelectorAll('.rank-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.rank-list').forEach(el=>el.classList.remove('active'));
  document.getElementById('rank-'+tab).classList.add('active');
}}

// 從法人買超／大戶動向／量增排行點擊個股，直接跳轉顯示該股票K線
function jumpToStock(sym) {{
  const s = ALL_STOCKS[sym];
  if(!s) return;
  showPage('monitor');
  document.querySelectorAll('.sector-row').forEach(r=>r.classList.remove('active'));
  resetHistoryToggle();
  document.getElementById('market-header').style.display='none';
  document.getElementById('sector-header').style.display='block';
  document.getElementById('history-chart').style.display='none';
  document.getElementById('chart-main').style.display='flex';
  document.getElementById('chart-main').style.flexDirection='column';

  document.getElementById('s-title').textContent=s.sectorEmoji+' '+s.name;
  document.getElementById('s-avg').textContent=s.chg;
  document.getElementById('s-avg').style.color=s.up==='true'?'#ff4444':'#22c55e';
  document.getElementById('s-rating').textContent=s.sectorName;
  document.getElementById('s-rating').style.color='#8b949e';
  document.getElementById('s-summary').textContent=`${{s.name}}（${{s.sectorName}}）現價 ${{s.price}}，${{s.instSignal}}。`;

  const tabsEl=document.getElementById('stock-tabs');
  tabsEl.innerHTML='';
  const btn=document.createElement('button');
  const isUp=s.up==='true';
  btn.className='stock-tab '+(isUp?'active-up':'active-down');
  btn.textContent=(s.star||'')+s.name+' '+s.chg;
  btn.onclick=()=>selectStock(s,btn,isUp);
  tabsEl.appendChild(btn);

  document.getElementById('stock-info-panel').style.display='block';
  selectStock(s,btn,isUp);
}}

// ---- 事件頁面：📊監控／📅事件 分頁切換、分類篩選、事件詳情 ----
function showPage(page) {{
  const isMonitor = page === 'monitor';
  document.getElementById('page-monitor').style.display = isMonitor ? 'grid' : 'none';
  document.getElementById('page-events').style.display = isMonitor ? 'none' : 'block';
  document.getElementById('nav-tab-monitor').classList.toggle('active', isMonitor);
  document.getElementById('nav-tab-events').classList.toggle('active', !isMonitor);
}}

let _currentEventFilter = '全部';
function filterEvents(btn, type) {{
  _currentEventFilter = type;
  document.querySelectorAll('.ev-chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  let visibleCount = 0;
  document.querySelectorAll('.ev-card').forEach(card=>{{
    const show = (type === '全部') || (card.dataset.type === type);
    card.style.display = show ? '' : 'none';
    if(show) visibleCount++;
  }});
  const emptyMsg = document.getElementById('ev-empty-msg');
  if(emptyMsg) emptyMsg.style.display = visibleCount === 0 ? '' : 'none';
}}

function showEventDetail(idx) {{
  const ev = EVENTS[idx];
  if(!ev) return;
  document.querySelectorAll('.ev-card').forEach((card,i)=>card.classList.toggle('active', i===idx));

  const isMarketWide = (ev.type === '總經' || ev.type === '升降息') && (!ev.impactStocks || ev.impactStocks.length === 0);

  const rows = (ev.impactStocks || []).map(s => {{
    const relCls = s.relation === '本尊' ? 'impact-relation self' : 'impact-relation';
    return `<tr onclick="jumpToStock('${{s.code}}.TW')" style="cursor:pointer">
      <td>${{s.name}}</td>
      <td>${{s.sector}}</td>
      <td><span class="${{relCls}}">${{s.relation}}</span></td>
      <td>${{s.impact}}</td>
    </tr>`;
  }}).join('');

  const impactSection = isMarketWide
    ? `<div class="impact-table-title">📋 影響範圍</div>
       <div class="ev-empty-msg" style="padding-top:20px">🌐 影響全市場，非個股事件</div>`
    : `<div class="impact-table-title">📋 影響個股</div>
       <table class="impact-table">
         <thead><tr><th>個股名稱</th><th>所屬族群</th><th>關聯性</th><th>預期影響</th></tr></thead>
         <tbody>${{rows || '<tr><td colspan="4" style="color:#8b949e;text-align:center">尚無關聯個股資料</td></tr>'}}</tbody>
       </table>`;

  document.getElementById('ev-detail-panel').innerHTML = `
    <div class="ev-detail-title">${{ev.title}}</div>
    <div class="ev-detail-meta">
      <span class="ev-detail-date">${{ev.date}}</span>
      <span class="ev-type-tag" style="background:#58a6ff22;color:#58a6ff;border:1px solid #58a6ff44">${{ev.type}}</span>
    </div>
    <div class="ev-detail-summary">${{ev.summary}}</div>
    ${{impactSection}}
  `;
}}

function selectSector(el, name, emoji, rating, summary, isUp, stocks) {{
  document.querySelectorAll('.sector-row').forEach(r=>r.classList.remove('active'));
  el.classList.add('active');

  resetHistoryToggle();
  document.getElementById('market-header').style.display='none';
  document.getElementById('sector-header').style.display='block';
  document.getElementById('history-chart').style.display='none';
  document.getElementById('chart-main').style.display='flex';
  document.getElementById('chart-main').style.flexDirection='column';

  const avgEl=el.querySelector('.val');
  document.getElementById('s-title').textContent=emoji+' '+name;
  document.getElementById('s-avg').textContent=avgEl.textContent;
  document.getElementById('s-avg').style.color=isUp?'#ff4444':'#22c55e';
  document.getElementById('s-rating').textContent=rating;
  document.getElementById('s-rating').style.color=isUp?'#ff4444':'#22c55e';
  document.getElementById('s-summary').textContent=summary;

  const tabsEl=document.getElementById('stock-tabs');
  tabsEl.innerHTML='';
  (stocks||[]).forEach((s,i)=>{{
    const btn=document.createElement('button');
    const isUp2=s.up==='true';
    btn.className='stock-tab'+(i===0?(isUp2?' active-up':' active-down'):'');
    btn.textContent=(s.star||'')+s.name+' '+s.chg;
    btn.onclick=()=>selectStock(s,btn,isUp2);
    tabsEl.appendChild(btn);
  }});

  document.getElementById('stock-info-panel').style.display='block';
  if(stocks&&stocks.length>0) selectStock(stocks[0],tabsEl.firstChild,stocks[0].up==='true');
}}

async function selectStock(s, btn, isUp) {{
  document.querySelectorAll('.stock-tab').forEach(t=>{{t.classList.remove('active-up');t.classList.remove('active-down');}});
  if(btn) btn.classList.add(isUp?'active-up':'active-down');
  document.getElementById('s-price').textContent=s.price;
  const chgEl=document.getElementById('s-chg');
  chgEl.textContent=s.chg; chgEl.style.color=isUp?'#ff4444':'#22c55e';
  document.getElementById('s-vol').textContent=s.vol;
  document.getElementById('s-vr').textContent=s.vr+'x';
  document.getElementById('s-entry').textContent=s.entry;
  document.getElementById('s-entry-note').textContent=s.entryNote;
  document.getElementById('s-stop').textContent=s.stop;
  document.getElementById('s-stop-note').textContent=s.stopNote;
  document.getElementById('s-target').textContent=s.target;
  document.getElementById('s-target-note').textContent=s.targetNote;
  document.getElementById('s-action').textContent=(s.star||'')+s.action;
  document.getElementById('s-action-note').textContent=s.actionNote;
  const foreignEl=document.getElementById('s-foreign');
  foreignEl.textContent=s.foreignFmt||'-';
  foreignEl.style.color=s.foreignUp==='true'?'#ff4444':'#22c55e';
  const trustEl=document.getElementById('s-trust');
  trustEl.textContent=s.trustFmt||'-';
  trustEl.style.color=s.trustUp==='true'?'#ff4444':'#22c55e';

  const kline=await fetchKline(s.sym);
  baseKData=kline||EMPTY_KLINE;
  renderKline();
}}

function backToMarket() {{
  document.getElementById('sector-header').style.display='none';
  document.getElementById('market-header').style.display='block';
  document.getElementById('stock-info-panel').style.display='none';
  resetHistoryToggle();
  document.getElementById('history-chart').style.display='none';
  document.getElementById('chart-main').style.display='flex';
  document.getElementById('chart-main').style.flexDirection='column';
  document.querySelectorAll('.sector-row').forEach(r=>r.classList.remove('active'));
  if(currentIndexKData) {{
    baseKData=currentIndexKData;
    renderKline();
  }}
}}

// 「📈 族群趨勢」切換鈕：K線區與族群評分趨勢折線圖互相切換，兩種模式下都可用
let _showingHistory = false;
function resetHistoryToggle() {{
  _showingHistory = false;
  const btn = document.getElementById('history-toggle-btn');
  btn.textContent = '📈 族群趨勢';
  btn.classList.remove('active-up');
}}
function toggleHistoryView() {{
  _showingHistory = !_showingHistory;
  const btn = document.getElementById('history-toggle-btn');
  if(_showingHistory) {{
    document.getElementById('chart-main').style.display='none';
    document.getElementById('history-chart').style.display='block';
    btn.textContent = '🕯️ K線圖';
    btn.classList.add('active-up');
    renderHistory();
  }} else {{
    document.getElementById('history-chart').style.display='none';
    document.getElementById('chart-main').style.display='flex';
    document.getElementById('chart-main').style.flexDirection='column';
    btn.textContent = '📈 族群趨勢';
    btn.classList.remove('active-up');
    renderKline();
  }}
}}

// 初始化：抓取大盤指數真實K線資料（大盤模式預設顯示K線，不是族群趨勢折線圖）
(async () => {{
  const twii=await fetchKline('TWII');
  if(twii) {{
    baseKData=twii;
    currentIndexKData=twii;
    renderKline();
    const info=updateIndexHeader(twii);
    document.getElementById('f-twii-val').textContent=fmtIdxNum(info.price);
    document.getElementById('f-twii-chg').textContent=`${{info.arrow}} ${{info.chg.toFixed(2)}}%`;
    document.getElementById('f-twii-chg').style.color=info.color;
    document.getElementById('f-fut-val').textContent=fmtIdxNum(info.price);
    document.getElementById('f-fut-chg').textContent=`${{info.arrow}} ${{info.chg.toFixed(2)}}%`;
    document.getElementById('f-fut-chg').style.color=info.color;
  }}
  const twoii=await fetchKline('TWOII');
  if(twoii) {{
    const n=twoii.c.length;
    const price=twoii.c[n-1];
    const prev=n>1?twoii.c[n-2]:price;
    const chg=prev?((price-prev)/prev*100):0;
    const color=chg>=0?'#ff4444':'#22c55e';
    const arrow=chg>=0?'▲':'▼';
    document.getElementById('f-twoii-val').textContent=fmtIdxNum(price);
    document.getElementById('f-twoii-chg').textContent=`${{arrow}} ${{chg.toFixed(2)}}%`;
    document.getElementById('f-twoii-chg').style.color=color;
  }}
}})();
</script>
</body>
</html>"""

    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ templates/index.html 已生成（v3 族群互動版）")

if __name__ == '__main__':
    generate()
