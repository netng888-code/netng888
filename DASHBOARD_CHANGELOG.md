# 持倉儀表板 index.html — 版本記錄

**Dashboard URL:** https://netng888-code.github.io/netng888/index.html  
**Finnhub API Key:** d83t8khr01qkm5c9fr50d83t8khr01qkm5c9fr5g

---

## 已確認正常功能清單

### ✅ 核心功能（一直正常）
- 美股持倉表格（US_HOLDINGS JS array，動態渲染）
- Finnhub 實時報價（18隻美股，60秒自動刷新）
- 港股報價（Yahoo Finance，CORS 問題，有 manual fallback）
- 已實現盈虧 banner（綠色滾動條）
- 今日盈虧 summary cards
- Flipcharts tab（TradingView iframe，每隻持倉股，含盤前/盤後）
- FV / GE 按鈕（Finviz + Google Finance 連結）

### ✅ Quicklinks Bar（頂部快速連結）
- **Manulife MPF** → https://netng888-code.github.io/netng888/manulife_mpf.html
- **My Watchlist** → https://netng888-code.github.io/netng888/mywatchlist.html
- Hover preview：**必須用靜態 HTML 卡片，不可用 iframe**
  - 原因：GitHub Pages 強制 `X-Frame-Options: deny`，iframe 永遠失敗
  - 本地 file:/// 開啟 iframe 可以，上到 GitHub 就 403/404
  - **正確方案：純 HTML/CSS 預覽卡，Watchlist 部份用 Finnhub API 取實時 %**
  - **2026-06-15 修正：已移除兩個 quicklink 的 onmouseover iframe preview**

### ✅ 個股 Hover Tooltip（美股持倉表格）
- 觸發：hover `#us-tbody` 內的 `.sym-badge`
- 觸發方式：`e.target.closest('#us-tbody .sym-badge')` ← 必須用此寫法
- 顯示內容：
  1. 股票名稱 + 實時價格/升跌（來自 `liveUS[sym]`）
  2. **Finnhub Candle API** 繪製 Canvas 蠟燭圖（90日，最後60根）
     - `https://finnhub.io/api/v1/stock/candle?symbol=X&resolution=D&from=...&to=...&token=KEY`
     - 自行用 Canvas drawCandleChart() 渲染，無依賴第三方
  3. Finnhub 公司新聞（過去7日，最多5條）
     - `https://finnhub.io/api/v1/company-news?symbol=X&from=...&to=...&token=KEY`
- **Finviz chart PNG 不可用**：有 hotlink protection，`<img src>` 直接載入會空白
- 新聞 cache：`newsCache[sym]`，同 session 只 fetch 一次
- Candle cache：`candleCache[sym]`，同 session 只 fetch 一次
- Tooltip 定位：`positionTT(badge)` 自動避開視窗邊緣

### ✅ Flipcharts 盤前/盤後（2026-06-10 新增）
- TradingView widget URL 加入 `&extended_hours=1`
- 所有持倉股（美股+港股）統一顯示盤前/盤後 K 線及價格標籤
- **注意**：各股票實際顯示效果取決於 TradingView 數據源授權，部份股票可能仍不完整

---

## 已知限制

| 功能 | 限制 | 備註 |
|------|------|------|
| 港股實時價 | Yahoo Finance CORS/cookie 問題 | 有手動輸入 fallback |
| Quicklinks iframe | GitHub Pages X-Frame-Options deny | 永久限制，只能用靜態卡片 |
| Finviz chart PNG | Hotlink protection | 改用 Finnhub Canvas 方案 |
| Finnhub 免費 API | 60次/分鐘 limit | 夠用，但 tooltip fetch 太快可能觸發 |

---

## 已知 Bug 記錄及修復

### ⚠️ Quicklinks Hover Preview 404（已修復 2026-06-15）
- **症狀**：hover Manulife MPF 或 My Watchlist 按鈕時，頁面彈出 GitHub Pages 404 錯誤視窗
- **根源**：兩個 quicklink 的 `onmouseover` iframe preview 指向本地路徑 `index_files/mywatchlist.htm` 及 `index_files/manulife_mpf.htm`，此路徑在 GitHub Pages 不存在
- **修復**：直接移除兩個 quicklink 的 `onmouseover`/`onmouseout` handler 及 iframe preview `<div>`，按鈕只保留點擊跳轉功能
- **教訓**：GitHub Pages 的 `X-Frame-Options: deny` 令任何 iframe preview 永遠無法運作，**日後不可再嘗試在 quicklinks 加入 iframe preview**

### ⚠️ Flipcharts Symbol Strip 重複顯示（已修復 2026-06-10）
- **症狀**：Flipcharts 的 symbol chip strip 顯示兩行（42個 chip），點擊 MU 等無反應，←→ 導航失效
- **根源**：HTML 靜態硬碼了 21 個 chip（舊版殘留），`initFlipcharts()` 執行時再 `appendChild` 一次，共 42 個 chip，index 錯亂
- **修復**：
  1. 清空 HTML 靜態 chip，只保留空容器 `<div class="flip-sym-strip" id="flip-sym-strip"></div>`
  2. `initFlipcharts()` 加入 `strip.innerHTML='';` 雙重保險
- **教訓**：日後修改 Flipcharts 時，**不可在 HTML 靜態寫 chip**，必須由 JS 動態生成

---

## 每次更新 CSV 的操作流程

1. 從 Futu 匯出 CSV（持倉保證金綜合帳戶 0193）
2. 上傳到 Claude Project Files
3. 告訴 Claude：「請根據最新 CSV 更新 index.html」
4. Claude 會：
   - `curl` 讀取 GitHub 上最新 index.html（**必須以此為基底，不可用本地快取版本**）
   - Python 字面字串替換 `US_HOLDINGS` JS array comment 日期
   - 核對 qty / cost 與 CSV 一致
5. 下載新 index.html → 上傳 GitHub 替換

---

## 文件結構

```
netng888-code/netng888 (GitHub repo)
├── index.html            ← 主持倉儀表板
├── manulife_mpf.html     ← MPF 強積金頁面
├── mywatchlist.html      ← 自選股 Watchlist
└── DASHBOARD_CHANGELOG.md ← 本文件
```

---

## 重要技術細節備忘

### US_HOLDINGS array 格式
```javascript
// 美股持倉（由Futu CSV更新，成本價/持倉數量靜態，實時價來自Finnhub）
const US_HOLDINGS = [
  { symbol:'MU',    name:'美光科技', qty:5,  cost:557.857, mktval:4537.50, pnl:1748.22, pnlPct:'+62.68%', realized:2395.49, todayPnL:0 },
  // ... 其餘持倉，按市值降序排列
];
```

### Regex anchor（Python 替換用）
```python
# 以中文 comment 行作 anchor（用字面字串替換，避免 regex 特殊字元問題）
old = '// ── 美股持倉（由Futu CSV 2026-XX-XX 匯出，按市值降序）────────────────────────'
new = '// ── 美股持倉（由Futu CSV 2026-YY-YY 匯出，按市值降序）────────────────────────'
content = content.replace(old, new)
```

### Flipcharts TradingView URL 參數（loadChart 函數）
```javascript
const url = `https://s.tradingview.com/widgetembed/?frameElementId=tv-chart`
  + `&symbol=${encodeURIComponent(tvSym)}`
  + `&interval=${flipInterval}`
  + `&hidesidetoolbar=0&hidetoptoolbar=0&symboledit=1&saveimage=1`
  + `&toolbarbg=0f1218`
  + `&studies=MASimple%40tv-basicstudies%1FMACD%40tv-basicstudies%1FVolume%40tv-basicstudies`
  + `&theme=dark&style=1&timezone=America%2FNew_York&withdateranges=1&showpopupbutton=1&locale=zh_TW&extended_hours=1`;
```

### Symbol Strip（initFlipcharts 函數）— 重要
```javascript
function initFlipcharts(){
  if(flipInited)return;
  const strip=document.getElementById('flip-sym-strip');
  strip.innerHTML='';   // ← 必須保留，防止靜態 HTML 殘留導致重複
  ALL_SYMS.forEach((sym,i)=>{ ... });
  ...
}
```
- HTML 中 `<div class="flip-sym-strip" id="flip-sym-strip"></div>` **必須是空的**
- 不可在 HTML 靜態寫入任何 chip div

### Quicklinks Bar — 重要限制
```html
<!-- 正確寫法（無 iframe，無 onmouseover） -->
<a class="qlink" href="https://netng888-code.github.io/netng888/manulife_mpf.html" target="_blank">
  <span class="qlink-icon">🏦</span> Manulife MPF
</a>
<a class="qlink" href="https://netng888-code.github.io/netng888/mywatchlist.html" target="_blank">
  <span class="qlink-icon">📋</span> My Watchlist
</a>
<!-- 錯誤：任何 iframe src 或 onmouseover iframe preview 在 GitHub Pages 均觸發 404 -->
```

### FINNHUB_KEY
```javascript
const FINNHUB_KEY = 'd83t8khr01qkm5c9fr50d83t8khr01qkm5c9fr5g';
```

### HK Holdings（手動維護）
```javascript
// ── 港股持倉（手動維護）
const HK_HOLDINGS = [
  { symbol:'7709', yahooSym:'7709.HK', name:'南方兩倍做多海力士', qty:200, cost:15.80,  ... },
  { symbol:'2367', yahooSym:'2367.HK', name:'巨子生物',           qty:600, cost:38.00,  ... },
  { symbol:'9988', yahooSym:'9988.HK', name:'阿里巴巴-W',         qty:100, cost:165.00, ... },
];
```

---

## 持倉快照記錄

### 2026-06-15（Futu CSV：最新美股持倉.csv）
**美股 18 隻持倉（按市值降序）：**

| 代碼 | 持倉 | 成本價 | 市值(USD) | 備註 |
|------|------|--------|-----------|------|
| MU   | 5    | $557.857 | 4,537.50 | 已鎖利 4 股 |
| GOOGL| 12   | $178.40  | 4,349.28 | |
| AVGO | 10   | $375.782 | 3,870.20 | |
| NVDA | 15   | $148.50  | 3,094.65 | |
| MRVL | 10   | $238.605 | 2,611.80 | |
| TER  | 5    | $92.00   | 1,846.65 | 長倉 +301% |
| META | 3    | $606.333 | 1,758.15 | |
| NOK  | 100  | $13.50   | 1,370.00 | |
| RDW  | 80   | $15.65   | 1,262.40 | |
| LEU  | 8    | $197.50  | 1,251.04 | 虧損 -20.82% |
| OKLO | 20   | $21.067  | 1,123.60 | +166% |
| RKLB | 10   | $76.00   | 1,079.20 | |
| PLTR | 7    | $124.335 | 921.13   | |
| ISRG | 2    | $453.10  | 855.16   | |
| LITE | 1    | $820.00  | 819.51   | |
| RR   | 300  | $2.445   | 687.00   | ↑ 從100股加至300股 |
| VRT  | 2    | $303.76  | 579.04   | |
| SERV | 30   | $11.743  | 213.00   | 虧損 -39.54% |

**變化摘要 vs 2026-06-10：**
- RR：100股 → 300股，成本 $2.735 → $2.445（加倉攤薄）
- 排序調整：OKLO(1,124) 移前 RKLB(1,079)（按市值降序）
- 排序調整：RR(687) 移前 VRT(579)（按市值降序）

**2026-06-15 技術修復：**
- 移除 Manulife MPF 及 My Watchlist quicklinks 的 `onmouseover` iframe preview
  - 原因：iframe 指向本地路徑 `index_files/*.htm`，GitHub Pages 上不存在，觸發 404 彈窗

---

### 2026-06-10（Futu CSV：019320260610101451）
**美股 18 隻持倉：**

| 代碼 | 持倉 | 成本價 | 備註 |
|------|------|--------|------|
| MU   | 5    | $557.857 | 已鎖利 |
| GOOGL| 12   | $178.40  | |
| AVGO | 10   | $375.782 | |
| NVDA | 15   | $148.50  | |
| MRVL | 10   | $238.605 | ↑ 從 5 股加至 10 股 |
| TER  | 5    | $92.00   | 長倉 +301% |
| META | 3    | $606.333 | |
| NOK  | 100  | $13.50   | 新加入 |
| RDW  | 80   | $15.65   | ↑ 從 30 股大幅加倉 |
| LEU  | 8    | $197.50  | 虧損 -20.82% |
| OKLO | 20   | $21.067  | +166% |
| RKLB | 10   | $76.00   | ↑ 從 5 股加至 10 股 |
| PLTR | 7    | $124.335 | |
| ISRG | 2    | $453.10  | |
| LITE | 1    | $820.00  | |
| VRT  | 2    | $303.76  | |
| RR   | 100  | $2.735   | |
| SERV | 30   | $11.743  | 虧損 -39.54% |

**2026-06-10 技術修復：**
- Flipcharts symbol strip 重複 bug 修復
- TradingView 加入 `&extended_hours=1`

*最後更新：2026-06-15*
