(function () {
  'use strict';
  const DATA = window.DASHBOARD_DATA;
  const CV = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const COLORS = {
    up: CV('--up'), down: CV('--down'), accent: CV('--accent'),
    fast: CV('--fast'), slow: CV('--slow'), ma60: CV('--ma60'), boll: CV('--boll'),
    surface: CV('--surface'), grid: CV('--grid'), border: CV('--border'),
    ink: CV('--ink'), inkMuted: CV('--ink-muted')
  };
  const PLOT_CONFIG = { responsive: true, displayModeBar: false, scrollZoom: true };

  const fmt = v => (v === null || v === undefined || isNaN(v)) ? '-' : (+v).toFixed(2);
  const fmtPct = v => (v === null || v === undefined) ? '-' : (v >= 0 ? '+' : '') + (+v).toFixed(2) + '%';
  const fmtNum = v => (v === null || v === undefined) ? '-' : (+v).toLocaleString('zh-TW', { maximumFractionDigits: 2 });

  // ============================================================
  // 導覽：首頁（含產業排行 Tab）／個股／自選股／事件
  // ============================================================
  const PAGES = ['home', 'stock', 'watch', 'events'];
  function showPage(page) {
    PAGES.forEach(p => {
      document.getElementById('page-' + p).classList.toggle('active', p === page);
      document.getElementById('nav-tab-' + p).classList.toggle('active', p === page);
    });
    if (page === 'home') renderHome();
    if (page === 'watch') renderWatchPage();
    if (page === 'events') renderEventsPage();
  }
  window.showPage = showPage;

  function switchHomeTab(btn, tab) {
    document.querySelectorAll('.home-tab').forEach(b => b.classList.toggle('active', b === btn));
    document.getElementById('home-tab-hot').style.display = tab === 'hot' ? 'block' : 'none';
    document.getElementById('home-tab-industry').style.display = tab === 'industry' ? 'block' : 'none';
    if (tab === 'industry') renderIndustryTab();
    else renderHomeEvents();
  }
  window.switchHomeTab = switchHomeTab;

  // ============================================================
  // 搜尋
  // ============================================================
  function initSearch() {
    const input = document.getElementById('stock-search-input');
    const results = document.getElementById('stock-search-results');
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      results.innerHTML = '';
      if (!q) { results.classList.remove('open'); return; }
      const matches = Object.entries(DATA.allStocks)
        .filter(([sym, s]) => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
        .slice(0, 8);
      if (matches.length === 0) { results.classList.remove('open'); return; }
      matches.forEach(([sym, s]) => {
        const row = document.createElement('div');
        row.className = 'search-result-row';
        row.innerHTML = `<span class="stock-name">${s.name}</span><span class="stock-code">${s.code}</span><span class="mono ${s.up === 'true' ? 'up' : 'down'}">${s.chg}</span>`;
        row.onclick = () => { openStock(sym); input.value = ''; results.classList.remove('open'); };
        results.appendChild(row);
      });
      results.classList.add('open');
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.nav-search')) results.classList.remove('open');
    });
  }

  // ============================================================
  // 首頁
  // ============================================================
  function renderHome() {
    const stockList = Object.values(DATA.allStocks);
    const trackedUp = stockList.filter(s => s.changePctRaw > 0).length;
    const trackedDown = stockList.filter(s => s.changePctRaw < 0).length;
    const mb = DATA.marketBreadth;
    const inst = DATA.latestInstitutionalTotal;
    const statsEl = document.getElementById('home-stats');
    statsEl.innerHTML = '';
    const cards = [
      mb
        ? { name: '台股上漲 / 下跌家數', num: `<span class="up">${mb.up}</span> / <span class="down">${mb.down}</span>`, chg: `平盤 ${mb.flat} 檔（${mb.market}共 ${mb.total} 檔；追蹤股票中 ${trackedUp}漲/${trackedDown}跌）` }
        : { name: '追蹤個股上漲 / 下跌家數', num: `<span class="up">${trackedUp}</span> / <span class="down">${trackedDown}</span>`, chg: `全市場家數尚無資料（共追蹤 ${stockList.length} 檔）` },
      { name: '三大法人合計買賣超', num: inst ? fmtSignedLots(inst.foreign + inst.trust + inst.dealer) : '-',
        chg: inst ? `外資 ${fmtSignedLots(inst.foreign)}　投信 ${fmtSignedLots(inst.trust)}` : `尚無資料`,
        cls: inst && (inst.foreign + inst.trust + inst.dealer) >= 0 ? 'up' : 'down' },
      { name: '今日最強族群', num: DATA.topSector, chg: '切換「產業排行」看完整排行' },
      { name: '市場情緒', num: DATA.sentiment.label, chg: DATA.updatedAt },
    ];
    cards.forEach(c => {
      statsEl.insertAdjacentHTML('beforeend', `<div class="card stat-card"><div class="name">${c.name}</div><div class="num ${c.cls || ''}">${c.num}</div><div class="chg">${c.chg}</div></div>`);
    });

    const hot = Object.entries(DATA.allStocks).sort((a, b) => b[1].changePctRaw - a[1].changePctRaw).slice(0, 8);
    const hb = document.getElementById('home-hot-stocks');
    hb.innerHTML = '';
    hot.forEach(([sym, s]) => hb.insertAdjacentHTML('beforeend', stockRowHtml(sym, s)));

    renderHomeEvents();
  }

  function renderHomeEvents() {
    document.getElementById('home-side-title').textContent = '最新事件';
    const evEl = document.getElementById('home-side-content');
    evEl.innerHTML = '';
    DATA.events.slice(-5).reverse().forEach(e => {
      evEl.insertAdjacentHTML('beforeend', `<a class="news-item"><span class="tag">${e.type}</span><span class="t">${e.date}</span>${e.title}</a>`);
    });
    if (DATA.events.length === 0) evEl.innerHTML = '<div class="rank-empty">近期沒有收錄到事件</div>';
  }

  function fmtSignedLots(n) {
    if (n === null || n === undefined) return '-';
    return (n >= 0 ? '+' : '') + n.toLocaleString('zh-TW') + '張';
  }

  function stockRowHtml(sym, s) {
    const up = s.up === 'true';
    return `<tr class="hover-row" onclick="window.openStock('${sym}')">
      <td><span class="stock-name">${s.name}</span><span class="stock-code">${s.code}</span></td>
      <td class="mono">${s.price}</td>
      <td class="mono ${up ? 'up' : 'down'}">${s.chg}</td>
      <td class="mono">${s.vol}</td>
      <td class="mono ${s.foreignUp === 'true' ? 'up' : 'down'}">${s.foreignFmt}</td>
    </tr>`;
  }

  // ============================================================
  // 產業排行（首頁「熱門個股」卡片內的 Tab）
  // ============================================================
  function renderIndustryTab() {
    const tb = document.getElementById('home-industry-table-body');
    tb.innerHTML = '';
    DATA.sectors.slice().sort((a, b) => b.avgChange - a.avgChange).forEach(s => {
      const up = s.avgChange >= 0;
      tb.insertAdjacentHTML('beforeend', `<tr class="hover-row" data-sector="${s.name}" onclick="window.showIndustryDetail('${s.name}')">
        <td>${s.emoji} ${s.name}</td>
        <td class="mono ${up ? 'up' : 'down'}">${fmtPct(s.avgChange)}</td>
        <td class="mono">${s.score}</td>
        <td class="mono">${s.totalVolume.toLocaleString()}</td>
        <td>${s.topStock}</td>
      </tr>`);
    });
    renderHomeEvents();
    document.querySelectorAll('#home-industry-table-body tr').forEach(r => r.classList.remove('active-row'));
  }
  function showIndustryDetail(sectorName) {
    const sector = DATA.sectors.find(s => s.name === sectorName);
    if (!sector) return;
    document.getElementById('home-side-title').textContent = `${sector.emoji} ${sector.name} 成分股`;
    const detail = document.getElementById('home-side-content');
    detail.innerHTML = `
      <div class="chip-row" id="industry-chip-row" style="padding:0 16px 16px"></div>
      <div class="industry-preview" id="industry-preview" style="display:none;margin:0 16px 16px;padding-top:16px">
        <div class="section-head" style="margin-bottom:8px">
          <h2 style="font-size:13px" id="industry-preview-name">-</h2>
          <button class="btn-sm active-up" id="industry-preview-btn">查看個股頁 →</button>
        </div>
        <div id="industry-preview-chart" style="height:360px"></div>
      </div>`;
    const chipRow = document.getElementById('industry-chip-row');
    let firstSym = null;
    sector.stocks.forEach(sym => {
      const s = DATA.allStocks[sym];
      if (!s) return;
      if (!firstSym) firstSym = sym;
      const chip = document.createElement('button');
      chip.className = 'chip';
      chip.textContent = `${s.name} ${s.chg}`;
      chip.style.color = s.up === 'true' ? COLORS.up : COLORS.down;
      chip.onclick = () => previewIndustryStock(sym, chip);
      chipRow.appendChild(chip);
    });
    document.querySelectorAll('#home-industry-table-body tr').forEach(r => r.classList.toggle('active-row', r.dataset.sector === sectorName));
    if (firstSym) previewIndustryStock(firstSym, chipRow.firstElementChild);
  }
  window.showIndustryDetail = showIndustryDetail;

  async function previewIndustryStock(sym, chipEl) {
    document.querySelectorAll('#industry-chip-row .chip').forEach(c => c.classList.remove('on'));
    if (chipEl) chipEl.classList.add('on');
    const s = DATA.allStocks[sym];
    if (!s) return;
    const panel = document.getElementById('industry-preview');
    panel.style.display = 'block';
    document.getElementById('industry-preview-name').textContent = `${s.name} ${s.code}　${s.chg}`;
    document.getElementById('industry-preview-btn').onclick = () => openStock(sym);
    const chartEl = document.getElementById('industry-preview-chart');
    chartEl.innerHTML = '';
    const k = await fetchKline(sym);
    if (!k || !k.dates.length) { chartEl.innerHTML = '<div class="rank-empty">尚無K線資料</div>'; return; }
    renderKlineInto('industry-preview-chart', k, false);
  }

  // ============================================================
  // 個股頁：搜尋/點擊進入，四個 Tab
  // ============================================================
  let currentStockSym = null;
  function openStock(sym) {
    const s = DATA.allStocks[sym];
    if (!s) return;
    currentStockSym = sym;
    showPage('stock');
    document.getElementById('stock-empty').style.display = 'none';
    document.getElementById('stock-content').style.display = 'block';

    const up = s.up === 'true';
    document.getElementById('sh-name').textContent = s.name;
    document.getElementById('sh-code').textContent = s.code;
    document.getElementById('sh-price').textContent = s.price;
    const chgEl = document.getElementById('sh-chg');
    chgEl.textContent = s.chg; chgEl.className = 'sh-chg ' + (up ? 'up' : 'down');
    document.getElementById('sh-vol').textContent = s.vol;
    document.getElementById('sh-vr').textContent = s.vr + 'x';
    document.getElementById('sh-pe').textContent = s.pe != null ? s.pe : '-';
    updateWatchBtn();

    document.getElementById('s-entry').textContent = s.entry;
    document.getElementById('s-entry-note').textContent = s.entryNote;
    document.getElementById('s-stop').textContent = s.stop;
    document.getElementById('s-stop-note').textContent = s.stopNote;
    document.getElementById('s-target').textContent = s.target;
    document.getElementById('s-target-note').textContent = s.targetNote;
    document.getElementById('s-action').textContent = (s.star || '') + s.action;
    document.getElementById('s-action-note').textContent = s.actionNote;

    document.getElementById('chip-foreign').textContent = s.foreignFmt;
    document.getElementById('chip-foreign').style.color = s.foreignUp === 'true' ? COLORS.up : COLORS.down;
    document.getElementById('chip-trust').textContent = s.trustFmt;
    document.getElementById('chip-trust').style.color = s.trustUp === 'true' ? COLORS.up : COLORS.down;
    document.getElementById('chip-signal').textContent = s.instSignal;
    document.getElementById('chip-holder').textContent = s.holderRatio != null ? s.holderRatio + '%' : '-';

    renderFundamentals(s);
    renderStockNews(s);
    drawChipTrend(s.code_bare);

    switchStockTabByName('tech');
    baseKData = EMPTY_KLINE;
    fetchKline(sym).then(k => { baseKData = k || EMPTY_KLINE; renderKline(); });
  }
  window.openStock = openStock;

  function switchStockTabByName(name) {
    document.querySelectorAll('.subtabbar button').forEach(b => b.classList.toggle('active', b.dataset.sub === name));
    document.querySelectorAll('.subpage').forEach(p => p.classList.toggle('active', p.id === 'sub-' + name));
    if (name === 'tech') setTimeout(renderKline, 0);
    if (name === 'chip') setTimeout(() => drawChipTrend(currentStockSym && DATA.allStocks[currentStockSym].code_bare), 0);
  }
  function switchStockTab(btn, name) { switchStockTabByName(name); }
  window.switchStockTab = switchStockTab;

  function renderFundamentals(s) {
    const grid = document.getElementById('fund-grid');
    const rows = [
      ['本益比 (PE)', s.pe], ['股價淨值比 (PB)', s.pb], ['殖利率', s.dividendYield != null ? s.dividendYield + '%' : null],
      ['每股盈餘 (EPS)', s.eps], ['月營收年增率', s.revenueYoy != null ? fmtPct(s.revenueYoy) : null],
      ['毛利率', s.grossMargin != null ? s.grossMargin + '%' : null], ['營業利益率', s.operatingMargin != null ? s.operatingMargin + '%' : null],
    ];
    grid.innerHTML = rows.map(([k, v]) => `<div class="kv-cell"><div class="k">${k}</div><div class="v">${v != null ? v : '-'}</div></div>`).join('');
  }

  function renderStockNews(s) {
    const el = document.getElementById('stock-news-list');
    const related = DATA.events.filter(e => (e.impactStocks || []).some(is => is.code === s.code_bare));
    if (related.length === 0) { el.innerHTML = '<div class="rank-empty">暫無相關新聞/事件</div>'; return; }
    el.innerHTML = related.slice().reverse().map(e =>
      `<a class="news-item"><span class="tag">${e.type}</span><span class="t">${e.date}</span>${e.title}</a>`
    ).join('');
  }

  function drawChipTrend(code) {
    const canvas = document.getElementById('chip-canvas');
    if (!canvas || canvas.offsetParent === null || !code) return;
    const rows = (DATA.institutionalHistory && DATA.institutionalHistory[code]) || [];
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = 200;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);
    if (rows.length === 0) {
      ctx.fillStyle = COLORS.inkMuted; ctx.font = '12px "Noto Sans TC"';
      ctx.fillText('尚無足夠歷史資料', 10, h / 2);
      return;
    }
    const padL = 44, padR = 10, padT = 10, padB = 20;
    const plotW = w - padL - padR, plotH = h - padT - padB;
    const maxAbs = Math.max(1, ...rows.map(r => Math.abs(r.foreign) + Math.abs(r.trust) + Math.abs(r.dealer))) * 0.6;
    const zeroY = padT + plotH / 2;
    const groupW = plotW / rows.length;
    ctx.strokeStyle = COLORS.border; ctx.beginPath(); ctx.moveTo(padL, zeroY); ctx.lineTo(w - padR, zeroY); ctx.stroke();
    const cols = { foreign: COLORS.fast, trust: COLORS.slow, dealer: COLORS.ma60 };
    rows.forEach((r, i) => {
      const cx = padL + i * groupW + groupW / 2;
      ['foreign', 'trust', 'dealer'].forEach((key, ki) => {
        const v = r[key];
        const bh = Math.abs(v) / maxAbs * (plotH / 2);
        const bw = groupW * 0.22;
        const bx = cx + (ki - 1) * bw * 1.15;
        ctx.fillStyle = cols[key];
        if (v >= 0) ctx.fillRect(bx - bw / 2, zeroY - bh, bw, bh);
        else ctx.fillRect(bx - bw / 2, zeroY, bw, bh);
      });
    });
    ctx.fillStyle = COLORS.inkMuted; ctx.font = '10px "IBM Plex Mono"';
    ctx.fillText(rows[0].date.slice(5), padL, h - 6);
    ctx.fillText(rows[rows.length - 1].date.slice(5), w - padR - 30, h - 6);
  }

  // ============================================================
  // 自選股（localStorage）／篩選器
  // ============================================================
  const WATCH_KEY = 'tw_dashboard_watchlist';
  function getWatchlist() { try { return JSON.parse(localStorage.getItem(WATCH_KEY) || '[]'); } catch (e) { return []; } }
  function setWatchlist(list) { localStorage.setItem(WATCH_KEY, JSON.stringify(list)); }
  function isWatched(sym) { return getWatchlist().includes(sym); }
  function toggleWatch() {
    if (!currentStockSym) return;
    let list = getWatchlist();
    if (list.includes(currentStockSym)) list = list.filter(s => s !== currentStockSym);
    else list.push(currentStockSym);
    setWatchlist(list);
    updateWatchBtn();
  }
  window.toggleWatch = toggleWatch;
  function updateWatchBtn() {
    const btn = document.getElementById('sh-watch-btn');
    if (!btn || !currentStockSym) return;
    const watched = isWatched(currentStockSym);
    btn.textContent = watched ? '★ 已在自選股' : '＋ 加入自選';
    btn.classList.toggle('active-up', watched);
  }

  function renderWatchPage() {
    const list = getWatchlist();
    const tb = document.getElementById('watch-body');
    const empty = document.getElementById('watch-empty');
    tb.innerHTML = '';
    if (list.length === 0) { empty.style.display = 'block'; } else { empty.style.display = 'none'; }
    list.forEach(sym => {
      const s = DATA.allStocks[sym];
      if (!s) return;
      const up = s.up === 'true';
      tb.insertAdjacentHTML('beforeend', `<tr class="hover-row">
        <td onclick="window.openStock('${sym}')"><span class="stock-name">${s.name}</span><span class="stock-code">${s.code}</span></td>
        <td class="mono" onclick="window.openStock('${sym}')">${s.price}</td>
        <td class="mono ${up ? 'up' : 'down'}" onclick="window.openStock('${sym}')">${s.chg}</td>
        <td class="mono" onclick="window.openStock('${sym}')">${s.pe != null ? s.pe : '-'}</td>
        <td><button class="btn-sm" onclick="window.removeFromWatch('${sym}')">移除</button></td>
      </tr>`);
    });
    renderScreenerChips();
  }
  function removeFromWatch(sym) { setWatchlist(getWatchlist().filter(s => s !== sym)); renderWatchPage(); }
  window.removeFromWatch = removeFromWatch;

  const SCREENER_CONDITIONS = [
    { id: 'foreign_buy', label: '外資5日買超', test: s => s.foreign5d > 0 },
    { id: 'trust_buy', label: '投信5日買超', test: s => s.trust5d > 0 },
    { id: 'inst_both', label: '法人同買', test: s => s.foreign5d > 0 && s.trust5d > 0 },
    { id: 'vol_high', label: '量比 > 1.5', test: s => s.volumeRatioRaw > 1.5 },
    { id: 'up_today', label: '今日上漲', test: s => s.changePctRaw > 0 },
    { id: 'pe_low', label: '本益比 < 20', test: s => s.pe != null && s.pe > 0 && s.pe < 20 },
    { id: 'yield_high', label: '殖利率 > 3%', test: s => s.dividendYield != null && s.dividendYield > 3 },
    { id: 'revenue_up', label: '月營收年增 > 0', test: s => s.revenueYoy != null && s.revenueYoy > 0 },
  ];
  let selectedConditions = new Set();
  function renderScreenerChips() {
    const el = document.getElementById('screener-chips');
    el.innerHTML = '';
    SCREENER_CONDITIONS.forEach(c => {
      const chip = document.createElement('button');
      chip.className = 'chip' + (selectedConditions.has(c.id) ? ' on' : '');
      chip.textContent = c.label;
      chip.onclick = () => {
        if (selectedConditions.has(c.id)) selectedConditions.delete(c.id); else selectedConditions.add(c.id);
        renderScreenerChips();
      };
      el.appendChild(chip);
    });
  }
  function applyScreener() {
    const active = SCREENER_CONDITIONS.filter(c => selectedConditions.has(c.id));
    const matches = Object.entries(DATA.allStocks).filter(([sym, s]) => active.every(c => c.test(s)));
    document.getElementById('screener-count').textContent = active.length === 0 ? '請至少勾選一個條件' : `符合 ${matches.length} 檔`;
    const tb = document.getElementById('screener-body');
    tb.innerHTML = '';
    matches.slice(0, 30).forEach(([sym, s]) => {
      const up = s.up === 'true';
      tb.insertAdjacentHTML('beforeend', `<tr>
        <td onclick="window.openStock('${sym}')" style="cursor:pointer"><span class="stock-name">${s.name}</span><span class="stock-code">${s.code}</span></td>
        <td class="mono">${s.price}</td>
        <td class="mono ${up ? 'up' : 'down'}">${s.chg}</td>
        <td><button class="btn-sm" onclick="window.addToWatch('${sym}')">＋ 自選</button></td>
      </tr>`);
    });
  }
  window.applyScreener = applyScreener;
  function addToWatch(sym) {
    const list = getWatchlist();
    if (!list.includes(sym)) { list.push(sym); setWatchlist(list); }
    renderWatchPage();
  }
  window.addToWatch = addToWatch;

  // ============================================================
  // 事件頁（沿用既有邏輯）
  // ============================================================
  let eventsRendered = false;
  function renderEventsPage() {
    if (eventsRendered) return;
    eventsRendered = true;
    const el = document.getElementById('ev-timeline');
    const emptyMsg = document.getElementById('ev-empty-msg');
    DATA.events.forEach((e, idx) => {
      const div = document.createElement('div');
      div.className = 'ev-card'; div.dataset.type = e.type; div.dataset.idx = idx;
      div.innerHTML = `<div class="ev-card-date">${e.date}</div><div class="ev-card-title">${e.title}</div>
        <span class="ev-type-tag" style="background:${COLORS.accent}22;color:${COLORS.accent};border:1px solid ${COLORS.accent}44">${e.type}</span>`;
      div.onclick = () => showEventDetail(idx);
      el.insertBefore(div, emptyMsg);
    });
    if (DATA.events.length === 0) emptyMsg.style.display = '';
  }
  let _currentEventFilter = '全部';
  function filterEvents(btn, type) {
    _currentEventFilter = type;
    document.querySelectorAll('.ev-chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    let visibleCount = 0;
    document.querySelectorAll('.ev-card').forEach(card => {
      const show = (type === '全部') || (card.dataset.type === type);
      card.style.display = show ? '' : 'none';
      if (show) visibleCount++;
    });
    document.getElementById('ev-empty-msg').style.display = visibleCount === 0 ? '' : 'none';
  }
  window.filterEvents = filterEvents;

  const IMPACT_DIRECTION_LABELS = {
    positive: ['impact-dir-positive', '利多'], negative: ['impact-dir-negative', '利空'], neutral: ['impact-dir-neutral', '中性']
  };
  function showEventDetail(idx) {
    const ev = DATA.events[idx];
    if (!ev) return;
    document.querySelectorAll('.ev-card').forEach((card, i) => card.classList.toggle('active', i === idx));
    let impactSection;
    if (ev.impactStocks && ev.impactStocks.length > 0) {
      const rows = ev.impactStocks.map(s => {
        const relCls = s.relation === '本尊' ? 'impact-relation self' : 'impact-relation';
        return `<tr><td><span class="impact-link" onclick="window.openStock('${s.symbol}')">${s.name}</span></td>
          <td>${s.sector}</td><td><span class="${relCls}">${s.relation}</span></td><td>${s.impact}</td>
          <td class="impact-reason">${s.reason}</td></tr>`;
      }).join('');
      impactSection = `<div class="impact-table-title">📋 影響個股</div><table class="impact-table">
        <thead><tr><th>個股名稱</th><th>所屬族群</th><th>關聯性</th><th>預期影響</th><th>原因</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    } else if (ev.affectedSectors && ev.affectedSectors.length > 0) {
      const rows = ev.affectedSectors.map(s => {
        const [cls, label] = IMPACT_DIRECTION_LABELS[s.direction] || IMPACT_DIRECTION_LABELS.neutral;
        return `<tr><td>${s.sectorLabel}</td><td><span class="${cls}">${label}</span></td><td class="impact-reason">${s.reason}</td></tr>`;
      }).join('');
      impactSection = `<div class="impact-table-title">📋 影響族群</div><table class="impact-table">
        <thead><tr><th>族群</th><th>預期方向</th><th>原因</th></tr></thead><tbody>${rows}</tbody></table>`;
    } else {
      impactSection = `<div class="impact-table-title">📋 影響範圍</div><div class="ev-empty-msg" style="padding-top:20px">🌐 影響全市場，非個股事件</div>`;
    }
    document.getElementById('ev-detail-panel').innerHTML = `
      <div class="ev-detail-title">${ev.title}</div>
      <div class="ev-detail-meta"><span class="ev-detail-date">${ev.date}</span>
        <span class="ev-type-tag" style="background:${COLORS.accent}22;color:${COLORS.accent};border:1px solid ${COLORS.accent}44">${ev.type}</span></div>
      <div class="ev-detail-summary">${ev.summary}</div>${impactSection}`;
  }

  // ============================================================
  // K線＋布林通道＋MA＋KD（沿用改版前邏輯，資料來源改為 fetch /api/kline/<symbol>）
  // ============================================================
  const klineCache = {};
  async function fetchKline(symbol) {
    if (klineCache[symbol]) return klineCache[symbol];
    try {
      const res = await fetch('/api/kline/' + encodeURIComponent(symbol));
      if (!res.ok) return null;
      const data = await res.json();
      if (!data.dates || data.dates.length === 0) return null;
      const result = {
        dates: data.dates, o: data.open, h: data.high, l: data.low, c: data.close, v: data.volume,
        colors: data.close.map((c, i) => c >= data.open[i] ? COLORS.up : COLORS.down)
      };
      klineCache[symbol] = result;
      return result;
    } catch (e) { console.error('K線資料取得失敗', symbol, e); return null; }
  }
  const EMPTY_KLINE = { dates: [], o: [], h: [], l: [], c: [], v: [], colors: [] };

  function calcMA(data, n) { return data.map((v, i, a) => i < n - 1 ? null : a.slice(i - n + 1, i + 1).reduce((s, x) => s + x, 0) / n); }
  function calcBoll(c, n = 20, k = 2) {
    const mid = calcMA(c, n); const upper = [], lower = [];
    for (let i = 0; i < c.length; i++) {
      if (i < n - 1) { upper.push(null); lower.push(null); continue; }
      const slice = c.slice(i - n + 1, i + 1); const mean = mid[i];
      const std = Math.sqrt(slice.reduce((s, x) => s + (x - mean) ** 2, 0) / n);
      upper.push(+(mean + k * std).toFixed(1)); lower.push(+(mean - k * std).toFixed(1));
    }
    return { mid, upper, lower };
  }
  function calcKD(h, l, c, n = 9) {
    const K = [], D = []; let k = 50, d = 50;
    for (let i = 0; i < c.length; i++) {
      const sliceH = h.slice(Math.max(0, i - n + 1), i + 1), sliceL = l.slice(Math.max(0, i - n + 1), i + 1);
      const hn = Math.max(...sliceH), ln = Math.min(...sliceL);
      const rsv = hn === ln ? 50 : (c[i] - ln) / (hn - ln) * 100;
      k = k * 2 / 3 + rsv / 3; d = d * 2 / 3 + k / 3;
      K.push(+k.toFixed(1)); D.push(+d.toFixed(1));
    }
    return { K, D };
  }

  let baseKData = EMPTY_KLINE, currentPeriod = '日';
  function aggregateData(base, period) {
    if (period === '日' || !base.dates || base.dates.length === 0) return base;
    const groupKey = (dateStr) => {
      if (period === '週') { const dt = new Date(dateStr); const day = dt.getDay() || 7; dt.setDate(dt.getDate() - day + 1); return dt.toISOString().split('T')[0]; }
      return dateStr.slice(0, 7);
    };
    const groups = {}, order = [];
    for (let i = 0; i < base.dates.length; i++) {
      const key = groupKey(base.dates[i]);
      if (!groups[key]) { groups[key] = { o: base.o[i], h: base.h[i], l: base.l[i], c: base.c[i], v: base.v[i], firstDate: base.dates[i] }; order.push(key); }
      else { const g = groups[key]; g.h = Math.max(g.h, base.h[i]); g.l = Math.min(g.l, base.l[i]); g.c = base.c[i]; g.v += base.v[i]; }
    }
    const dates = [], o = [], h = [], l = [], c = [], v = [], colors = [];
    order.forEach(key => { const g = groups[key]; dates.push(g.firstDate); o.push(g.o); h.push(g.h); l.push(g.l); c.push(g.c); v.push(g.v); colors.push(g.c >= g.o ? COLORS.up : COLORS.down); });
    return { dates, o, h, l, c, v, colors };
  }

  let _klineInfo = null;
  function showKlineInfoAt(idx) {
    const info = _klineInfo;
    if (!info || idx == null || idx < 0 || idx >= info.dates.length) return;
    document.getElementById('ki-date').textContent = info.dates[idx];
    document.getElementById('ki-open').textContent = fmt(info.o[idx]);
    document.getElementById('ki-high').textContent = fmt(info.h[idx]);
    document.getElementById('ki-low').textContent = fmt(info.l[idx]);
    document.getElementById('ki-close').textContent = fmt(info.c[idx]);
    document.getElementById('ki-ma5').textContent = fmt(info.ma5[idx]);
    document.getElementById('ki-ma20').textContent = fmt(info.ma20[idx]);
    document.getElementById('ki-ma60').textContent = fmt(info.ma60[idx]);
    document.getElementById('ki-bollu').textContent = fmt(info.bollU[idx]);
    document.getElementById('ki-bolld').textContent = fmt(info.bollL[idx]);
    document.getElementById('ki-k').textContent = fmt(info.kdK[idx]);
    document.getElementById('ki-d').textContent = fmt(info.kdD[idx]);
    document.getElementById('ki-vol').textContent = (info.v[idx] / 100000000).toFixed(2) + '億';
  }

  function renderKline() {
    const canvas = document.getElementById('mainChart');
    if (!canvas || canvas.offsetParent === null) return;
    const d = aggregateData(baseKData, currentPeriod);
    renderKlineInto('mainChart', d, true);
  }

  // 個股頁K線圖(技術分析Tab)與產業排行成分股預覽共用同一套繪圖邏輯，
  // 確保候選股/成分股點出來的圖跟個股頁看到的是同一張圖(K線+MA5/20/60+布林通道+KD+成交量)，
  // 差別只在後者不需要互動式十字線資訊列(interactive=false)。
  function renderKlineInto(divId, d, interactive) {
    if (!d.dates || d.dates.length === 0) return;
    const boll = calcBoll(d.c), kd = calcKD(d.h, d.l, d.c);
    const ma5 = calcMA(d.c, 5), ma20 = calcMA(d.c, 20), ma60 = calcMA(d.c, 60);

    const maxIdx = d.dates.length - 1;
    const tickvals = d.dates.filter((_, i) => i % 10 === 0);
    const ticktext = tickvals.map(x => x.slice(5));
    const spike = { showspikes: true, spikemode: 'across', spikesnap: 'cursor', spikecolor: COLORS.accent, spikethickness: 1, spikedash: 'dash' };
    const hasVolume = d.v.some(v => v > 0);

    const traces = [
      { type: 'candlestick', x: d.dates, open: d.o, high: d.h, low: d.l, close: d.c, xaxis: 'x', yaxis: 'y',
        increasing: { line: { color: COLORS.up }, fillcolor: COLORS.up }, decreasing: { line: { color: COLORS.down }, fillcolor: COLORS.down }, name: 'K線' },
      { x: d.dates, y: ma5, type: 'scatter', mode: 'lines', line: { color: COLORS.fast, width: 1 }, name: 'MA5', xaxis: 'x', yaxis: 'y' },
      { x: d.dates, y: ma20, type: 'scatter', mode: 'lines', line: { color: COLORS.slow, width: 1 }, name: 'MA20', xaxis: 'x', yaxis: 'y' },
      { x: d.dates, y: ma60, type: 'scatter', mode: 'lines', line: { color: COLORS.ma60, width: 1 }, name: 'MA60', xaxis: 'x', yaxis: 'y' },
      { x: d.dates, y: boll.upper, type: 'scatter', mode: 'lines', line: { color: COLORS.boll, width: 0.8, dash: 'dot' }, name: '布林上', showlegend: false, xaxis: 'x', yaxis: 'y' },
      { x: d.dates, y: boll.lower, type: 'scatter', mode: 'lines', line: { color: COLORS.boll, width: 0.8, dash: 'dot' }, name: '布林下', fill: 'tonexty', fillcolor: 'rgba(138,145,127,0.08)', showlegend: false, xaxis: 'x', yaxis: 'y' },
      { x: d.dates, y: kd.K, type: 'scatter', mode: 'lines', line: { color: COLORS.fast, width: 1.2 }, name: 'K', xaxis: 'x', yaxis: 'y2' },
      { x: d.dates, y: kd.D, type: 'scatter', mode: 'lines', line: { color: COLORS.slow, width: 1.2 }, name: 'D', xaxis: 'x', yaxis: 'y2' },
      { x: [d.dates[0], d.dates[maxIdx]], y: [80, 80], type: 'scatter', mode: 'lines', line: { color: COLORS.border, width: 0.8, dash: 'dot' }, showlegend: false, hoverinfo: 'skip', xaxis: 'x', yaxis: 'y2' },
      { x: [d.dates[0], d.dates[maxIdx]], y: [20, 20], type: 'scatter', mode: 'lines', line: { color: COLORS.border, width: 0.8, dash: 'dot' }, showlegend: false, hoverinfo: 'skip', xaxis: 'x', yaxis: 'y2' },
    ];
    if (hasVolume) traces.push({ x: d.dates, y: d.v, type: 'bar', marker: { color: d.colors, opacity: 0.8 }, name: '成交量', xaxis: 'x', yaxis: 'y3' });
    const annotations = hasVolume ? [] : [{ text: '無成交量資料', xref: 'paper', yref: 'paper', x: 0.5, y: 0.075, showarrow: false, font: { color: COLORS.inkMuted, size: 10 } }];

    Plotly.newPlot(divId, traces, {
      paper_bgcolor: COLORS.surface, plot_bgcolor: COLORS.surface, font: { color: COLORS.inkMuted, size: 10 },
      margin: { l: 50, r: 8, t: 4, b: 20 }, showlegend: false, dragmode: 'pan', hovermode: 'x unified', annotations,
      xaxis: { gridcolor: COLORS.grid, showgrid: true, zeroline: false, rangeslider: { visible: false }, type: 'category', range: [0, maxIdx], tickmode: 'array', tickvals, ticktext, ...spike },
      yaxis: { gridcolor: COLORS.grid, showgrid: true, zeroline: false, side: 'right', fixedrange: true, domain: [0.35, 1.0], showspikes: true },
      yaxis2: { gridcolor: COLORS.grid, showgrid: true, zeroline: false, side: 'right', fixedrange: true, domain: [0.18, 0.32], range: [0, 100], dtick: 40, showspikes: true },
      yaxis3: { gridcolor: COLORS.grid, showgrid: true, zeroline: false, side: 'right', fixedrange: true, domain: [0, 0.15], showticklabels: false, showspikes: true }
    }, PLOT_CONFIG);

    if (interactive) {
      _klineInfo = { dates: d.dates, o: d.o, h: d.h, l: d.l, c: d.c, v: d.v, ma5, ma20, ma60, bollU: boll.upper, bollL: boll.lower, kdK: kd.K, kdD: kd.D };
      attachZoomBound(divId, maxIdx);
      attachShiftWheelPan(divId);
      attachMainHover(divId);
      showKlineInfoAt(maxIdx);
    }
  }

  function attachZoomBound(divId, maxIdx) {
    const div = document.getElementById(divId);
    let syncing = false;
    div.removeAllListeners && div.removeAllListeners('plotly_relayout');
    div.on('plotly_relayout', (ev) => {
      if (syncing) return;
      let x0 = ev['xaxis.range[0]'], x1 = ev['xaxis.range[1]'];
      if (x0 === undefined && ev['xaxis.range']) { x0 = ev['xaxis.range'][0]; x1 = ev['xaxis.range'][1]; }
      if (x0 === undefined || x1 === undefined) return;
      let nx0 = x0, nx1 = x1; const width = nx1 - nx0;
      if (width >= maxIdx) { nx0 = 0; nx1 = maxIdx; }
      else { if (nx0 < 0) { nx1 -= nx0; nx0 = 0; } if (nx1 > maxIdx) { nx0 -= (nx1 - maxIdx); nx1 = maxIdx; } if (nx0 < 0) nx0 = 0; }
      if (Math.abs(nx0 - x0) > 1e-6 || Math.abs(nx1 - x1) > 1e-6) { syncing = true; Plotly.relayout(div, { 'xaxis.range': [nx0, nx1] }); syncing = false; }
    });
  }
  function attachShiftWheelPan(divId) {
    const div = document.getElementById(divId);
    if (div._shiftPanBound) return;
    div._shiftPanBound = true;
    div.addEventListener('wheel', function (ev) {
      if (!ev.shiftKey) return;
      ev.preventDefault(); ev.stopPropagation();
      const layout = div.layout;
      if (!layout || !layout.xaxis || !layout.xaxis.range) return;
      const [x0, x1] = layout.xaxis.range; const span = x1 - x0;
      const shift = span * 0.15 * (ev.deltaY > 0 ? 1 : -1);
      Plotly.relayout(div, { 'xaxis.range': [x0 + shift, x1 + shift] });
    }, { passive: false });
  }
  function attachMainHover(divId) {
    const div = document.getElementById(divId);
    if (div._hoverBound) return;
    div._hoverBound = true;
    div.on('plotly_hover', (ev) => { if (!ev.points || !ev.points.length) return; const p = ev.points[0]; showKlineInfoAt((p.pointIndex !== undefined) ? p.pointIndex : p.pointNumber); });
    div.on('plotly_unhover', () => { if (_klineInfo) showKlineInfoAt(_klineInfo.dates.length - 1); });
  }
  function setPeriod(btn) {
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPeriod = btn.textContent;
    renderKline();
  }
  window.setPeriod = setPeriod;

  // ============================================================
  // init
  // ============================================================
  initSearch();
  renderHome();
})();
