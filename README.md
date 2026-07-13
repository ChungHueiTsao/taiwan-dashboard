# 🇹🇼 台股族群每日監控系統

每天早上 8:50 自動更新，追蹤 13 大台股熱門族群強弱趨勢。

## 監控族群
⛰️ 神山群 | 💡 IC設計 | ❄️ 散熱 | 🔮 石英元件 | 🔧 被動元件
💎 矽晶圓 | ⚡ 功率元件 | 🔆 光通訊 | 🟩 PCB/CCL | 💾 記憶體
🚁 國防無人機 | 🏭 重電 | 🤖 AI設備封測

## 本地執行

```bash
pip install -r requirements.txt
python app.py
```

開啟瀏覽器：http://127.0.0.1:8080

## 手動立刻更新

```bash
# 方法1：瀏覽器點擊「立即更新」按鈕
# 方法2：直接執行
python data_collector.py
python analyzer.py
python dashboard_generator.py
```

## 部署到 Render（免費雲端）

1. 將此專案推送到 GitHub
2. 前往 https://render.com 用 GitHub 登入
3. New → Web Service → 選擇此 repository
4. 設定：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
   - Plan: Free
5. 部署完成後取得網址，例如：
   `https://taiwan-stock-dashboard.onrender.com`

## 功能說明

- **族群強弱排行**：13大族群由強到弱排列，含評級、漲跌幅、進度條
- **族群漲跌幅圖**：Plotly 互動長條圖
- **歷史趨勢圖**：近20個交易日各族群評分折線圖
- **個股明細**：點擊族群卡片展開，顯示個股現價、漲跌幅、量比
- **自動更新**：週一到週五 08:50 自動執行，頁面每60秒自動刷新
