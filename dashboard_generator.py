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

    # 左側族群列表
    sector_rows_html = ""
    for i, s in enumerate(sectors):
        change = s['avg_change']
        color = "#ff4444" if change > 0 else "#22c55e"
        sign = "+" if change > 0 else ""
        score_pct = max(3, min(97, s['score']))
        is_up = "true" if change > 0 else "false"

        # 個股資料 for JS（進場/停損/目標/操作建議均由 data_collector.py 的 ATR+籌碼邏輯計算）
        stocks_js = []
        stock_items = list(s.get('stocks', {}).items())
        stock_items_sorted = sorted(stock_items, key=lambda x: x[1].get('change_pct', 0), reverse=True)
        for sym, sd in stock_items_sorted[:5]:
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

            stocks_js.append({
                "name": sd.get('name', sym),
                "code": sym.replace('.TW','').replace('.TWO',''),
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
                "foreignFmt": f"{'+' if foreign_5d>=0 else ''}{foreign_5d:,}張",
                "trustFmt": f"{'+' if trust_5d>=0 else ''}{trust_5d:,}張",
                "foreignUp": "true" if foreign_5d >= 0 else "false",
                "trustUp": "true" if trust_5d >= 0 else "false",
                "instSignal": inst_signal,
                "star": star,
                "up": c_color
            })

        summary = f"{s['name']}族群今日平均{sign}{change:.2f}%，{s['rating']}。領漲個股為{s['top_stock']}（{'+' if s['top_change']>0 else ''}{s['top_change']:.2f}%），籌碼面建議留意法人動向與量能變化。"

        sector_rows_html += f"""
        <div class="sector-row" onclick='selectSector(this,{json.dumps(s['name'])},{json.dumps(s['emoji'])},{json.dumps(s['rating'])},{json.dumps(summary)},{is_up},{json.dumps(stocks_js)})'>
          <span class="rank">{i+1}</span>
          <span class="name">{s['emoji']} {s['name']}</span>
          <span class="val" style="color:{color}">{sign}{change:.2f}%</span>
          <div class="bar-wrap"><div class="bar-bg"><div class="bar-fill" style="width:{score_pct}%;background:{color}"></div></div></div>
        </div>
        {"<hr class='divider'>" if i == sum(1 for x in sectors if x['avg_change']>0)-1 and i < len(sectors)-1 else ""}"""

    # Plotly 歷史折線圖
    line_traces = ""
    colors = ["#58a6ff","#ff4444","#22c55e","#eab308","#a855f7","#f97316","#06b6d4","#ec4899","#84cc16","#f43f5e","#8b5cf6","#14b8a6","#fb923c"]
    for i, s in enumerate(sectors[:13]):
        name = s['name']
        if name in history_data:
            hd = history_data[name]
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
.nav .meta{{display:flex;align-items:center;gap:8px;font-size:11px;color:#8b949e}}
.badge{{padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600}}
.btn-sm{{background:#21262d;border:1px solid #30363d;color:#8b949e;padding:3px 10px;border-radius:4px;font-size:11px;cursor:pointer}}
.btn-sm:hover{{background:#30363d;color:#e6edf3}}
.main{{display:grid;grid-template-columns:240px 1fr;height:calc(100vh - 38px);overflow:hidden}}
/* LEFT */
.left{{border-right:1px solid #30363d;padding:8px 6px;display:flex;flex-direction:column;gap:2px;overflow-y:auto}}
.left-title{{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;padding:0 4px;margin-bottom:4px;flex-shrink:0}}
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
.chart-main{{flex:1;padding:4px 14px 0;min-height:0}}
.chart-kd{{padding:0 14px;height:54px;border-top:1px solid #21262d;flex-shrink:0}}
.chart-kd-label{{font-size:9px;color:#8b949e;padding:2px 0}}
.chart-vol{{padding:0 14px;height:50px;border-top:1px solid #21262d;flex-shrink:0}}
.chart-vol-label{{font-size:9px;color:#8b949e;padding:2px 0}}
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
  <h1>🇹🇼 台股族群每日監控</h1>
  <div class="meta">
    <span>最後更新：{updated_at}</span>
    <span style="font-size:9px;color:#8b949e">（資料延遲約15分鐘）</span>
    <span class="badge" style="background:{sentiment['color']}22;color:{sentiment['color']};border:1px solid {sentiment['color']}44">{sentiment['label']}</span>
    <button class="btn-sm" onclick="location.href='/api/refresh?redirect=1'">🔄 立即更新</button>
  </div>
</div>

<div class="main">
  <!-- ===== LEFT ===== -->
  <div class="left">
    <div class="left-title">📊 族群強弱排行</div>
    {sector_rows_html}
  </div>

  <!-- ===== RIGHT ===== -->
  <div class="right">

    <!-- 大盤模式 Header -->
    <div class="right-header" id="market-header">
      <div class="idx-tabs">
        <button class="idx-btn active" onclick="switchIndex(this,'^TWII','加權指數')">加權指數</button>
        <button class="idx-btn" onclick="switchIndex(this,'^TWOII','OTC 櫃買')">OTC 櫃買</button>
        <button class="idx-btn" onclick="switchIndex(this,'^TWII','台指期')">台指期</button>
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
    </div>

    <!-- K線主圖 -->
    <div class="chart-main" id="chart-main">
      <div id="klineChart" style="width:100%;height:100%"></div>
    </div>

    <!-- 歷史趨勢（大盤模式） -->
    <div class="history-chart" id="history-chart">
      <div id="historyChart" style="width:100%;height:100%"></div>
    </div>

    <!-- KD副圖 -->
    <div class="chart-kd">
      <div class="chart-kd-label">KD &nbsp;
        <span style="color:#f97316">K: <span id="kd-k">--</span></span>&nbsp;
        <span style="color:#58a6ff">D: <span id="kd-d">--</span></span>
      </div>
      <div id="kdChart" style="width:100%;height:38px"></div>
    </div>

    <!-- 成交量副圖 -->
    <div class="chart-vol">
      <div class="chart-vol-label">成交量 &nbsp;<span id="vol-label" style="color:#e6edf3">--</span></div>
      <div id="volChart" style="width:100%;height:34px"></div>
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

<script>
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

function renderKline() {{
  const d=aggregateData(baseKData,currentPeriod);
  if(!d.dates||d.dates.length===0) return;
  const boll=calcBoll(d.c); const kd=calcKD(d.h,d.l,d.c);
  const ma5=calcMA(d.c,5),ma20=calcMA(d.c,20),ma60=calcMA(d.c,60);

  // K線
  Plotly.newPlot('klineChart',[
    {{type:'candlestick',x:d.dates,open:d.o,high:d.h,low:d.l,close:d.c,
      increasing:{{line:{{color:'#ff4444'}},fillcolor:'#ff4444'}},
      decreasing:{{line:{{color:'#22c55e'}},fillcolor:'#22c55e'}},name:'K線'}},
    {{x:d.dates,y:ma5,type:'scatter',mode:'lines',line:{{color:'#f97316',width:1}},name:'MA5'}},
    {{x:d.dates,y:ma20,type:'scatter',mode:'lines',line:{{color:'#58a6ff',width:1}},name:'MA20'}},
    {{x:d.dates,y:ma60,type:'scatter',mode:'lines',line:{{color:'#a855f7',width:1}},name:'MA60'}},
    {{x:d.dates,y:boll.upper,type:'scatter',mode:'lines',line:{{color:'#8b949e',width:0.8,dash:'dot'}},name:'布林上',showlegend:false}},
    {{x:d.dates,y:boll.lower,type:'scatter',mode:'lines',line:{{color:'#8b949e',width:0.8,dash:'dot'}},name:'布林下',
      fill:'tonexty',fillcolor:'rgba(139,148,158,0.04)',showlegend:false}},
  ],{{
    ...DARK_LAYOUT,
    margin:{{l:50,r:8,t:4,b:20}},
    showlegend:false,
    dragmode:'pan',
    xaxis:{{...DARK_LAYOUT.xaxis,rangeslider:{{visible:false}},type:'category',
      range:[0,d.dates.length-1],
      tickmode:'array',
      tickvals:d.dates.filter((_,i)=>i%10===0),
      ticktext:d.dates.filter((_,i)=>i%10===0).map(x=>x.slice(5))}},
    yaxis:{{...DARK_LAYOUT.yaxis,fixedrange:true}}
  }},PLOT_CONFIG);

  // KD
  const lastK=kd.K[kd.K.length-1],lastD=kd.D[kd.D.length-1];
  document.getElementById('kd-k').textContent=lastK;
  document.getElementById('kd-d').textContent=lastD;
  Plotly.newPlot('kdChart',[
    {{x:d.dates,y:kd.K,type:'scatter',mode:'lines',line:{{color:'#f97316',width:1.2}},name:'K',showlegend:false}},
    {{x:d.dates,y:kd.D,type:'scatter',mode:'lines',line:{{color:'#58a6ff',width:1.2}},name:'D',showlegend:false}},
    {{x:[d.dates[0],d.dates[d.dates.length-1]],y:[80,80],type:'scatter',mode:'lines',
      line:{{color:'#30363d',width:0.8,dash:'dot'}},showlegend:false}},
    {{x:[d.dates[0],d.dates[d.dates.length-1]],y:[20,20],type:'scatter',mode:'lines',
      line:{{color:'#30363d',width:0.8,dash:'dot'}},showlegend:false}},
  ],{{
    ...DARK_LAYOUT,
    margin:{{l:50,r:8,t:0,b:14}},
    xaxis:{{...DARK_LAYOUT.xaxis,showticklabels:false,type:'category',range:[0,d.dates.length-1]}},
    yaxis:{{...DARK_LAYOUT.yaxis,range:[0,100],dtick:40,fixedrange:true}}
  }},PLOT_CONFIG);

  // 成交量
  const lastVol=d.v[d.v.length-1];
  document.getElementById('vol-label').textContent=(lastVol/100000000).toFixed(0)+'億';
  Plotly.newPlot('volChart',[
    {{x:d.dates,y:d.v,type:'bar',marker:{{color:d.colors,opacity:0.8}},showlegend:false}}
  ],{{
    ...DARK_LAYOUT,
    margin:{{l:50,r:8,t:0,b:14}},
    xaxis:{{...DARK_LAYOUT.xaxis,showticklabels:false,type:'category',range:[0,d.dates.length-1]}},
    yaxis:{{...DARK_LAYOUT.yaxis,showticklabels:false,fixedrange:true}}
  }},PLOT_CONFIG);

  attachZoomSync(d.dates);
}}

// K線縮放/平移時，限制在資料範圍內，並同步 KD、成交量副圖
let _zoomSyncing = false;
function attachZoomSync(dates) {{
  const klineDiv = document.getElementById('klineChart');
  const maxIdx = dates.length - 1;
  klineDiv.removeAllListeners && klineDiv.removeAllListeners('plotly_relayout');
  klineDiv.on('plotly_relayout', (ev) => {{
    if(_zoomSyncing) return;
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

    _zoomSyncing = true;
    if(Math.abs(nx0 - x0) > 1e-6 || Math.abs(nx1 - x1) > 1e-6) {{
      Plotly.relayout(klineDiv, {{'xaxis.range':[nx0,nx1]}});
    }}
    Plotly.relayout('kdChart', {{'xaxis.range':[nx0,nx1]}});
    Plotly.relayout('volChart', {{'xaxis.range':[nx0,nx1]}});
    _zoomSyncing = false;
  }});
}}

// 歷史趨勢圖
function renderHistory() {{
  const traces=[{line_traces}];
  if(traces.length===0) return;
  Plotly.newPlot('historyChart',traces,{{
    ...DARK_LAYOUT,
    margin:{{l:40,r:8,t:4,b:30}},
    showlegend:true,
    legend:{{bgcolor:'#161b22',bordercolor:'#30363d',borderwidth:1,font:{{size:9}}}},
    xaxis:{{...DARK_LAYOUT.xaxis,type:'category'}},
    yaxis:{{...DARK_LAYOUT.yaxis,title:'強勢評分'}}
  }},PLOT_CONFIG);
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
  updateIndexHeader(kline);
  renderKline();
}}

function setPeriod(btn) {{
  document.querySelectorAll('.period-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  currentPeriod=btn.textContent;
  renderKline();
}}

function selectSector(el, name, emoji, rating, summary, isUp, stocks) {{
  document.querySelectorAll('.sector-row').forEach(r=>r.classList.remove('active'));
  el.classList.add('active');

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
  document.getElementById('history-chart').style.display='block';
  document.getElementById('chart-main').style.display='none';
  document.querySelectorAll('.sector-row').forEach(r=>r.classList.remove('active'));
  renderHistory();
}}

// 初始化：抓取大盤指數真實資料，並顯示歷史趨勢圖
(async () => {{
  document.getElementById('chart-main').style.display='none';
  document.getElementById('history-chart').style.display='block';
  renderHistory();

  const twii=await fetchKline('^TWII');
  if(twii) {{
    baseKData=twii;
    renderKline();
    const info=updateIndexHeader(twii);
    document.getElementById('f-twii-val').textContent=fmtIdxNum(info.price);
    document.getElementById('f-twii-chg').textContent=`${{info.arrow}} ${{info.chg.toFixed(2)}}%`;
    document.getElementById('f-twii-chg').style.color=info.color;
    document.getElementById('f-fut-val').textContent=fmtIdxNum(info.price);
    document.getElementById('f-fut-chg').textContent=`${{info.arrow}} ${{info.chg.toFixed(2)}}%`;
    document.getElementById('f-fut-chg').style.color=info.color;
  }}
  const twoii=await fetchKline('^TWOII');
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
