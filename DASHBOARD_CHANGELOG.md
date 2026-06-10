# 持倉儀表板 index.html — 版本記錄

**Dashboard URL:** https://netng888-code.github.io/netng888/index.html  
**Finnhub API Key:** d83t8khr01qkm5c9fr50d83t8khr01qkm5c9fr5g

---

## 已確認正常功能清單

### ✅ 核心功能（一直正常）
- 美股持倉表格（US_HOLDINGS JS array，動態渲染）
- Finnhub 實時報價（17隻美股，60秒自動刷新）
- 港股報價（Yahoo Finance，CORS 問題，有 manual fallback）
- 已實現盈虧 banner（綠色滾動條）
- 今日盈虧 summary cards
- Flipcharts tab（TradingView iframe，每隻持倉股）
- FV / GE 按鈕（Finviz + Google Finance 連結）

### ✅ Quicklinks Bar（頂部快速連結）
- **Manulife MPF** → https://netng888-code.github.io/netng888/manulife_mpf.html
- **My Watchlist** → https://netng888-code.github.io/netng888/mywatchlist.html
- Hover preview：**必須用靜態 HTML 卡片，不可用 iframe**
  - 原因：GitHub Pages 強制 `X-Frame-Options: deny`，iframe 永遠失敗
  - 本地 file:/// 開啟 iframe 可以，上到 GitHub 就 403
  - **正確方案：純 HTML/CSS 預覽卡，Watchlist 部份用 Finnhub API 取實時 %**

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

---

## 已知限制

| 功能 | 限制 | 備註 |
|------|------|------|
| 港股實時價 | Yahoo Finance CORS/cookie 問題 | 有手動輸入 fallback |
| Quicklinks iframe | GitHub Pages X-Frame-Options deny | 永久限制，只能用靜態卡片 |
| Finviz chart PNG | Hotlink protection | 改用 Finnhub Canvas 方案 |
| Finnhub 免費 API | 60次/分鐘 limit | 夠用，但 tooltip fetch 太快可能觸發 |

---

## 每次更新 CSV 的操作流程

1. 從 Futu 匯出 CSV（持倉保證金綜合帳戶 0193）
2. 上傳到 Claude Project Files
3. 告訴 Claude：「請根據最新 CSV 更新 index.html」
4. Claude 會：
   - `curl` 讀取 GitHub 上的 index.html
   - Python `re.sub` 替換 `US_HOLDINGS` JS array
   - 更新 footer 日期、risk card 文字
5. 下載新 index.html → 上傳 GitHub 替換

---

## 文件結構

```
netng888-code/netng888 (GitHub repo)
├── index.html          ← 主持倉儀表板
├── manulife_mpf.html   ← MPF 強積金頁面
└── mywatchlist.html    ← 自選股 Watchlist
```

---

## 重要技術細節備忘

### US_HOLDINGS array 格式
```javascript
// 美股持倉（由Futu CSV更新，成本價/持倉數量靜態，實時價來自Finnhub）
const US_HOLDINGS = [
  { symbol:'GOOGL', name:'谷歌-A',   qty:12, cost:178.40, mktval:0 },
  // ... 其餘持倉
];
```

### Regex anchor（Python 替換用）
```python
# 以中文 comment 行作 anchor
re.sub(r'(// 美股持倉.*?\n)const US_HOLDINGS = \[.*?\];',
       replacement, content, flags=re.DOTALL)
```

### FINNHUB_KEY
```javascript
const FINNHUB_KEY = 'd83t8khr01qkm5c9fr50d83t8khr01qkm5c9fr5g';
```

---

---

## 持倉快照記錄

### 2026-06-10（Futu CSV：019320260610101451）
**美股 18 隻持倉：**

| 代碼 | 持倉 | 成本價 | 備註 |
|------|------|--------|------|
| MU   | 7    | $557.857 | ↓ 從早前減持（原有更多） |
| GOOGL| 12   | $178.40  | 已鎖利賣出 8 股 @~$400 |
| AVGO | 10   | $375.782 | |
| NVDA | 15   | $148.50  | 已鎖利賣出部份 @~$222 |
| MRVL | 10   | $238.605 | ↑ 從 5 股加至 10 股 |
| TER  | 5    | $92.00   | 長倉，高盈利 +301% |
| META | 3    | $606.333 | 輕微虧損 -3.35% |
| NOK  | 100  | $13.50   | 新加入（2026-06-10 首見）|
| RDW  | 80   | $15.65   | ↑ 從 30 股大幅加倉 |
| LEU  | 8    | $197.50  | 虧損 -20.82%，風險股 |
| OKLO | 20   | $21.067  | 高盈利 +166% |
| RKLB | 10   | $76.00   | ↑ 從 5 股加至 10 股 |
| PLTR | 7    | $124.335 | |
| ISRG | 2    | $453.10  | 輕微虧損 -5.63% |
| LITE | 1    | $820.00  | 幾乎持平 |
| VRT  | 2    | $303.76  | 輕微虧損 -4.69% |
| RR   | 100  | $2.735   | 小型持倉，虧損 -16% |
| SERV | 30   | $11.743  | 虧損 -39.54%，風險股 |

**變化摘要 vs 上次（2026-06-07）：**
- MRVL：5 → 10（加倉）
- RKLB：5 → 10（加倉）
- RDW：30 → 80（大幅加倉）
- NOK：新加入 100 股 @$13.50
- GitHub index.html 已於 2026-06-10 更新至此版本

*最後更新：2026-06-10*
