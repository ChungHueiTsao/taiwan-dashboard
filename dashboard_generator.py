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
    kline_map = {}
    for i, s in enumerate(sectors):
        change = s['avg_change']
        color = "#ff4444" if change > 0 else "#22c55e"
        sign = "+" if change > 0 else ""
        score_pct = max(3, min(97, s['score']))
        is_up = "true" if change > 0 else "false"

        # 個股資料 for JS
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
            # 簡單建議計算
            entry_low = round(p * 0.98, 1)
            entry_high = round(p * 1.01, 1)
            stop = round(p * 0.91, 1)
            target = round(p * 1.15, 1)
            if c > 2:
                action = "強勢追進"
                action_note = "放量突破可追"
            elif c > 0.5:
                action = "積極買進"
                action_note = "趨勢偏多"
            elif c > -0.5:
                action = "觀察等待"
                action_note = "整理格局"
            else:
                action = "暫時觀望"
                action_note = "等止跌訊號"

            if sd.get('kline'):
                kline_map[sym] = sd['kline']

            stocks_js.append({
                "name": sd.get('name', sym),
                "code": sym.replace('.TW','').replace('.TWO',''),
                "sym": sym,
                "price": str(p),
                "chg": f"{c_sign}{c:.2f}%",
                "vol": f"{v:,}",
                "vr": f"{vr:.1f}",
                "entry": f"{entry_low}～{entry_high}",
                "stop": str(stop),
                "target": str(target),
                "action": action,
                "entryNote": "回測支撐進場" if c > 0 else "反彈確認再進",
                "stopNote": "跌破月線出場",
                "targetNote": f"波段+15%目標",
                "actionNote": action_note,
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

    kline_map_json = json.dumps(kline_map, ensure_ascii=False)

    os.makedirs('templates', exist_ok=True)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="60">
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
.info-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:6px}}
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
        <button class="idx-btn active" onclick="switchIndex(this,'加權指數','46,892','▼ 312 (-0.66%)','#22c55e','47,120','47,204','46,601','3,842億')">加權指數</button>
        <button class="idx-btn" onclick="switchIndex(this,'OTC 櫃買','298.45','▼ 2.51 (-0.83%)','#22c55e','300.1','301.2','297.8','850億')">OTC 櫃買</button>
        <button class="idx-btn" onclick="switchIndex(this,'台指期','46,750','▼ 330 (-0.70%)','#22c55e','47,080','47,150','46,520','12,845口')">台指期</button>
      </div>
      <div class="idx-val">
        <span class="big" id="idx-price">46,892</span>
        <span id="idx-chg" style="font-size:12px;font-weight:600;color:#22c55e">▼ 312 (-0.66%)</span>
        <span style="font-size:10px;color:#8b949e">{updated_at}</span>
      </div>
      <div class="ohlc" id="idx-ohlc">
        <span>開 47,120</span><span>高 47,204</span><span>低 46,601</span><span>量 3,842億</span>
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
      <button class="period-btn" onclick="setPeriod(this)">1分</button>
      <button class="period-btn" onclick="setPeriod(this)">5分</button>
      <button class="period-btn" onclick="setPeriod(this)">15分</button>
      <button class="period-btn" onclick="setPeriod(this)">30分</button>
      <button class="period-btn" onclick="setPeriod(this)">60分</button>
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
        <div class="f-val">46,892</div>
        <div class="f-chg" style="color:#22c55e">▼ -0.66%</div>
      </div>
      <div class="idx-footer-card">
        <div class="f-name">OTC 櫃買</div>
        <div class="f-val">298.45</div>
        <div class="f-chg" style="color:#22c55e">▼ -0.83%</div>
      </div>
      <div class="idx-footer-card">
        <div class="f-name">台指期</div>
        <div class="f-val">46,750</div>
        <div class="f-chg" style="color:#22c55e">▼ -0.70%</div>
      </div>
    </div>
  </div>
</div>

<script>
const STOCK_KLINE = {kline_map_json};
const PLOT_CONFIG = {{responsive:true,displayModeBar:false}};
const DARK_LAYOUT = {{
  paper_bgcolor:'#0d1117',plot_bgcolor:'#0d1117',
  font:{{color:'#8b949e',size:10}},
  margin:{{l:40,r:8,t:4,b:20}},
  xaxis:{{gridcolor:'#21262d',showgrid:true,zeroline:false}},
  yaxis:{{gridcolor:'#21262d',showgrid:true,zeroline:false,side:'right'}}
}};

// ---- 模擬 K 線資料 ----
function genKlineData(n, base, vol) {{
  const dates=[],o=[],h=[],l=[],c=[],v=[],colors=[];
  let p=base;
  const now=new Date();
  for(let i=n;i>=0;i--) {{
    const d=new Date(now); d.setDate(d.getDate()-i);
    if(d.getDay()===0||d.getDay()===6) continue;
    dates.push(d.toISOString().split('T')[0]);
    const chg=(Math.random()-0.5)*0.04;
    const op=p; const cl=+(p*(1+chg)).toFixed(1);
    const hi=+(Math.max(op,cl)*(1+Math.random()*0.01)).toFixed(1);
    const lo=+(Math.min(op,cl)*(1-Math.random()*0.01)).toFixed(1);
    o.push(op); h.push(hi); l.push(lo); c.push(cl);
    colors.push(cl>=op?'#ff4444':'#22c55e');
    v.push(Math.floor(vol*(0.5+Math.random())));
    p=cl;
  }}
  return {{dates,o,h,l,c,v,colors}};
}}

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

let kData = genKlineData(60, 46892, 3800000000);

function renderKline() {{
  const d=kData;
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
    xaxis:{{...DARK_LAYOUT.xaxis,rangeslider:{{visible:false}},type:'category',
      tickmode:'array',
      tickvals:d.dates.filter((_,i)=>i%10===0),
      ticktext:d.dates.filter((_,i)=>i%10===0).map(x=>x.slice(5))}},
    yaxis:{{...DARK_LAYOUT.yaxis}}
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
    xaxis:{{...DARK_LAYOUT.xaxis,showticklabels:false,type:'category'}},
    yaxis:{{...DARK_LAYOUT.yaxis,range:[0,100],dtick:40}}
  }},PLOT_CONFIG);

  // 成交量
  const lastVol=d.v[d.v.length-1];
  document.getElementById('vol-label').textContent=(lastVol/100000000).toFixed(0)+'億';
  Plotly.newPlot('volChart',[
    {{x:d.dates,y:d.v,type:'bar',marker:{{color:d.colors,opacity:0.8}},showlegend:false}}
  ],{{
    ...DARK_LAYOUT,
    margin:{{l:50,r:8,t:0,b:14}},
    xaxis:{{...DARK_LAYOUT.xaxis,showticklabels:false,type:'category'}},
    yaxis:{{...DARK_LAYOUT.yaxis,showticklabels:false}}
  }},PLOT_CONFIG);
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
function switchIndex(btn, name, price, chg, chgColor, open, high, low, vol) {{
  document.querySelectorAll('.idx-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('idx-price').textContent=price;
  const chgEl=document.getElementById('idx-chg');
  chgEl.textContent=chg; chgEl.style.color=chgColor;
  document.getElementById('idx-ohlc').innerHTML=
    `<span>開 ${{open}}</span><span>高 ${{high}}</span><span>低 ${{low}}</span><span>量 ${{vol}}</span>`;
  kData=genKlineData(60,parseFloat(price.replace(',','')),3800000000);
  renderKline();
}}

function setPeriod(btn) {{
  document.querySelectorAll('.period-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const periods={{'1分':1,'5分':5,'15分':15,'30分':30,'60分':60,'日':1,'週':1,'月':1}};
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
    btn.textContent=s.name+' '+s.chg;
    btn.onclick=()=>selectStock(s,btn,isUp2);
    tabsEl.appendChild(btn);
  }});

  document.getElementById('stock-info-panel').style.display='block';
  if(stocks&&stocks.length>0) selectStock(stocks[0],tabsEl.firstChild,stocks[0].up==='true');
}}

function selectStock(s, btn, isUp) {{
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
  document.getElementById('s-action').textContent=s.action;
  document.getElementById('s-action-note').textContent=s.actionNote;
  const real=STOCK_KLINE[s.sym];
  if(real&&real.dates&&real.dates.length>1) {{
    kData={{dates:real.dates,o:real.o,h:real.h,l:real.l,c:real.c,v:real.v,colors:real.colors}};
  }} else {{
    const base=parseFloat(s.price)||10000;
    kData=genKlineData(60,base,Math.floor(3000000+Math.random()*5000000));
  }}
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

// 初始化
renderKline();
// 預設大盤模式顯示歷史趨勢
document.getElementById('chart-main').style.display='none';
document.getElementById('history-chart').style.display='block';
renderHistory();
</script>
</body>
</html>"""

    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ templates/index.html 已生成（v3 族群互動版）")

if __name__ == '__main__':
    generate()
