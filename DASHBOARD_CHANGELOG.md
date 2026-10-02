# 持倉監控系統 — 技術參考與版本記錄

> 最後更新：2026-10-02　｜　取代舊版（舊版只涵蓋 index.html，停留喺 2026-06-15、18隻持倉）
> **呢份係「格式規格＋歷史記錄」，唔等於任何檔案嘅現時實際內容。兩者有出入時，以檔案本身（Project Files 或 GitHub live）為準。**
> 唔好喺呢份文件入面放任何真實 API key／token／密碼（GitHub repo 公開）。

**Dashboard：** https://netng888-code.github.io/netng888/
**Repo：** https://github.com/netng888-code/netng888
**Raw 基底：** `https://raw.githubusercontent.com/netng888-code/netng888/main/<路徑>`

---

## 0. 讀檔規則（Claude 必讀）

1. **先喺 Project Files 搵**（`/mnt/project/`）。
2. 搵唔到、或者懷疑過時 → 用 `curl -s` 攞 GitHub raw（見下表路徑）。
3. 修改任何會上傳 GitHub 嘅檔案前，**必須以 GitHub live 版本做 base**，唔可以用對話內舊結果、本機暫存或呢份文件嘅描述。
4. 用 raw URL 或者 `github.com/.../tree/main/<folder>` 嘅 HTML 頁睇目錄；**唔好用 api.github.com**（無 token 好快撞 rate limit，2026-10-02 實測會 403）。
5. raw 有幾分鐘 CDN 緩存，剛 push 完未必即時見到。
6. 中文檔名要 URL encode（例如 `CTA_GEX_監視工具學習記錄_20260614.md`）。

### 檔案地圖（2026-10-02 核實）

| 檔案 | Project Files | GitHub raw 路徑 | 備註 |
|---|---|---|---|
| `gex_chart_v5_terminal.html` | ✅ | `gex_chart_v5_terminal.html` | 主終端，上傳 GitHub 替換 |
| `index.html` | ✅ | `index.html` | 持倉儀表板（GitHub Pages 首頁） |
| `mywatchlist.html` | ✅ | `mywatchlist.html` | Watchlist |
| `global-indices.html` | ✅ | `global-indices.html` | 全球指數 |
| `premarket-rates-monitor.html` | ✅ | `premarket-rates-monitor.html` | 美日息率（頁面標題「最新息率」） |
| `secreport.html` | ❌ | `secreport.html` | SEC 財報分析頁，Project Files 冇 |
| `manulife_mpf.html` | ❌ | `manulife_mpf.html` | MPF 頁 |
| `futu_bridge_v2.py` | ✅（v3.16，見下） | **冇**（root 404） | 本機專用，永遠唔 push |
| `why_moving_bridge_patch.py` | ✅ | **冇** | 貼入 bridge 嘅區塊，見 §5 |
| `telegram_bot.py` | ✅（v1.24） | `telegram/telegram_bot.txt`（⚠️ 備份只係 v1.9，已過時） | GitHub 係 `.txt` |
| `github_gex_updater.py` | ✅ | `telegram/github_gex_updater.txt` | GitHub 係 `.txt` |
| `cftc_cot_updater.py` | ✅ | **冇** | 輸出寫入 `cot/*.md` |
| `telegram/telegram.md` | ❌ | `telegram/telegram.md` | Bot 架構文件 |
| `DASHBOARD_CHANGELOG.md` | ❌ | `DASHBOARD_CHANGELOG.md` | 本文件 |
| CTA/GEX 學習記錄 | ❌ | `CTA_GEX_監視工具學習記錄_20260614.md`（repo root；`notes/` 路徑 404） | 宏觀框架 |
| `cot/ES_COT.md`、`cot/NQ_COT.md` | ❌ | 同路徑 | 每週六自動更新 |
| `stocks/*.md`、`stocks/README.md` | ❌ | 同路徑 | 每日 GEX 快照（Futu 離線時 fallback） |
| 持倉 CSV | ✅ `holdings_US_20261001.csv`、港股 `…20260527港股.csv` | — | 由 Futu 匯出 |

---

## 1. 系統架構

```
Futu OpenD (127.0.0.1:11111, US LV3 + Options LV1)
   └─ futu_bridge_v2.py（FastAPI :8888，本機）
        ├─ /api/quote /gex /moneyflow /kline /capital_dist /capital_flow
        ├─ /api/fundamentals(/{sym})   Futu snapshot + Finnhub 補
        ├─ /api/real_indices /macro_quotes   Futu(HSI,ASHR代理) + Yahoo
        ├─ /api/yield_curve /yield_curve_jp   Treasury XML / 日本 MOF CSV
        ├─ /api/options_calendar /sec_financials /sec_analysis
        ├─ /api/ai_analysis/{sym}   OpenRouter → DeepSeek（主）→ GLM（備）
        └─ /api/why_moving/{sym}    歸因（Python 統計 + AI 講解）
              ↑ 前端：gex_chart_v5_terminal.html / global-indices.html /
                       premarket-rates-monitor.html / secreport.html
github_gex_updater.py（排程 09:00 + 21:00 HKT）→ GitHub stocks/*.md
cftc_cot_updater.py（排程 週六 08:00 HKT）→ GitHub cot/*.md
telegram_bot.py（長期運行）← 讀 Futu bridge / GitHub md → Telegram
```

---

## 2. 版本現況（2026-10-02）

| 組件 | 版本 | 備註 |
|---|---|---|
| gex_chart_v5_terminal.html | **v5.34**（本次交付）；GitHub 上係 v5.33 | v5.34 修正「點解升跌」新聞截斷 |
| futu_bridge_v2.py | Project Files 係 v3.16；本機運行版已包含 why_moving 區塊（v3.17.x） | 區塊獨立存喺 `why_moving_bridge_patch.py`，最新 **v3.17.2** |
| telegram_bot.py | v1.24（Project Files）；GitHub 備份 v1.9 ⚠️ | 改 bot 前以 Project Files 為準 |
| cftc_cot_updater.py | v1.2（含 REQUIRED_FIELDS schema 診斷） | |
| global-indices.html | v7 | |
| premarket-rates-monitor.html | v5 | 美債 + JGB + 美日息差 + 重疊圖 |

**AI 模型鏈（bridge v3.15 / bot v1.23 起）：** 主 `deepseek/deepseek-v4-flash-0731`，備 `z-ai/glm-5.3-flash`（兩個都用釘死版本 slug，唔用 `-latest` alias）。請求帶 `provider.sort=latency`、`max_tokens=2000`、`reasoning:{effort:low, exclude:true}`；content 為空／403／逾時 → 自動 fallback。

**排程（Windows 工作排程器，本機 `C:\Users\Dell\Downloads\FUTU\telegram\`）：** `github_gex_updater.py` 09:00＋21:00 HKT；`cftc_cot_updater.py` 週六 08:00 HKT。

---

## 3. 持倉快照（Futu CSV 2026-10-01，美股 17 隻）

| 代碼 | 持股 | 平均成本 |
|---|---|---|
| GOOGL | 20 | 245.04 |
| NVDA | 20 | 189.0625 |
| AVGO | 10 | 378.602 |
| MRVL | 10 | 257.303 |
| NOK | 200 | 12.458 |
| TER | 5 | 92.00 |
| META | 3 | 606.333 |
| RDW | 40 | 15.65 |
| LEU | 8 | 197.50 |
| OKLO | 40 | 30.05875 |
| RKLB | 10 | 76.00 |
| PLTR | 12 | 127.304 |
| ISRG | 2 | 453.10 |
| LYTE | 30 | 25.00 |
| RR | 300 | 2.445 |
| VRT | 2 | 303.76 |
| SERV | 30 | 11.743 |

港股（CSV 係 2026-05-27，**已過時**；index.html 手動維護）：07709 200@15.80、02367 600@38.00、09988 100@165.00。

已清倉：MU（2026-09-03 @1,000，已實現 +442.14）、LITE（2026-08 @940，+120）。

⚠️ index.html 入面 qty/cost 已同步，但 `mktval/pnl`、風險概覽卡文字（例如 LEU、SERV 數字）係舊快照靜態字串，唔代表最新；實時價由 Finnhub 覆蓋。

---

## 4. 買賣處理規則（五檔同步）

每次買賣必須同步：
1. 持倉 CSV（Project Files 用）
2. `index.html`：`US_HOLDINGS`（qty/cost/mktval/pnl/pnlPct/realized/todayPnL）、靜態表格行、已實現利潤橫額、summary card、footer 更新記錄
3. `gex_chart_v5_terminal.html`：`PORTFOLIO` object、`HOLDINGS` quicklinks 陣列、tab 標題「持倉總覽 (N)」、changelog
4. `futu_bridge_v2.py`：`US_STOCKS`
5. `telegram_bot.py`：`ALL_HOLDINGS`（`VALID_SYMS` 自動跟隨）
6. `github_gex_updater.py`：`BATCH1`／`BATCH2`（新持倉加落 BATCH2 或第三個 Barchart 帳戶，唔好加落帳戶1：quota 18/20）

歷史 changelog 條目一律凍結，全局替換時唔好改舊條目，只改現況顯示字串。

---

## 5. 交付與驗證流程（強制）

- HTML：交付完整檔案；Python：以 `.txt` 交付（`.py` 下載會失敗，用戶本機改名）。
- 驗證：① `node --check`（先抽出 inline JS）② HTML tag-balance（排除 `<script>`/`<style>`）③ `python3 -m py_compile` ＋ `pyflakes` ④ 同 GitHub 原檔 diff，確認只改咗預期行。
- 改完 bridge／bot 要手動重啟先生效（`telegram_bot.py` 唔會 auto-reload）。
- `why_moving_bridge_patch.py` 用法：成段貼入 `futu_bridge_v2.py`，位置喺「指數/期貨/ETF代碼可用性診斷（v2.3）」區塊**之前**；替換舊 `<<<WHY_MOVING_BEGIN>>>…<<<WHY_MOVING_END>>>` 整段。

---

## 6. 重要規則與已知教訓

**架構／GEX**
- 方向、距離、分級判斷一律喺 Python `if/else` 預先計好（`compute_wall_status`、`compute_breakout_scenario`、`compute_retail_dealer_context`），AI 只負責組織語言，唔准自己計方向（AVGO 事件教訓）。
- Futu SDK 單一 `_ctx`：Futu call 只可 sequential 或 `max_workers ≤ 4`；純 HTTP（Yahoo/Treasury）先可以大量並行。
- `BREAKOUT_BUFFER_PCT = 0.5` 喺前端、bridge 兩邊人手同步；NYSE 假期表喺 html／bridge／bot 三處人手同步。
- Put Wall > Call Wall 喺單一到期日 OI 集中時可以合法出現，唔係 bug。
- Premium Flow 正常但 Order Book／Tick Delta／K線同時失敗 → 訂閱 slot 爆，撳「🔄 重置連接」（`/api/reset`）。
- `dividend_ratio_ttm` 已係百分比（20＝20%）；虧損股 P/E 負數或 null 顯示「—」。
- 前端 `AbortSignal.timeout` 一定要大過 backend 理論 worst-case（多次出事：AI 分析、跑馬燈、孳息曲線）。

**今日點解升跌（`/api/why_moving/{sym}`，前端 v5.31 起）**
- 日線收市價迴歸（估計窗口 60 日、唔包今日）：大市(SPY)／板塊ETF／公司特定殘差(z 值)，加 10Y／WTI／BTC／VIX／DXY 宏觀 verdict 同 Dealer(GEX) 背景。
- 每個因素 verdict（主要／次要／背景／不支持／未見異動／證據不足）由 Python 判定，AI 唔准推翻或升降級。
- 新聞按發布時間對比走勢窗口（前一交易日 16:00 ET → 最近交易日 16:00 ET）分類：窗口內／收市後／窗口前／時間未知。收市後新聞唔可以解釋今次升跌。
- 手動貼入新聞（textarea → `extra_news`，最多 15 行、每行 200 字）永遠標「時間未知」。
- ⚠️ **2026-10-02 bug（v5.34／bridge v3.17.2 修正）**：手動新聞排清單最尾，前端 `slice(0,8)` 切走；AI prompt 又只叫揀「窗口內」新聞，貼入內容被完全忽略。教訓：往 list 加新來源要諗清楚排序同前端截斷，並提供「已收到 N 條」確認。
- 已知結構性盲點：ADR（SKHY）嘅海外本地時段走勢會被當「公司特定殘差」；未來可加本地市場因子（例如 `000660.KS`／EWY）。

**SEC XBRL**：用多 tag fallback（NVDA 首個 tag 可能只喺舊財年出現）；現金流量表只有 YTD → `_sec_ytd_buckets` + `_derive_ytd_quarters`；GOOGL 冇 GrossProfit tag → Revenue − Cost of Revenue；用真實期間日期去重，唔用 SEC 嘅 fy/fp。

**index.html 舊教訓（仍然有效）**
- GitHub Pages `X-Frame-Options: deny`：quicklinks 唔可以做 iframe preview。
- Finviz chart PNG 有 hotlink protection，唔可 `<img>` 直載。
- Flipcharts symbol strip 由 JS 動態生成，HTML 必須保持空容器，`initFlipcharts()` 要 `strip.innerHTML=''`。
- TradingView embed 用純 ticker symbol，唔強制交易所前綴；cash index（SPX/HSI 等）會彈授權窗，改用 ETF 代理或真實點數 ticker。
- 港股實時價靠 Yahoo，瀏覽器有 CORS 問題，有手動 fallback。

**其他**
- GitHub 上嘅 python 備份係佔位 key（`YOUR_xxx`），真 key 只喺用戶本機。
- Finnhub 免費 60 次/分鐘；Barchart 免費帳戶約 20 page views/日。

---

## 7. 近期版本記錄（新→舊）

- **2026-10-02** html v5.34／bridge 區塊 v3.17.2：修正「點解升跌」手動新聞唔顯示（見 §6）；同日重寫本文件同 `telegram/telegram.md`。html v5.33：美股表刪「名稱」欄、操作欄統一 TV／FV／GE／SEC／OC 文字掣。
- **2026-10-01** html v5.31／v5.32、bridge v3.17.1（歸因窗口＋新聞時間分類）、bot v1.24（GOOGL 20 股、NVDA 20 股、移除 MU）。
- 2026-09-28 html v5.30：OptionCharts 外鏈、三套主題（白天／黑夜／陰天）；premarket-rates-monitor v5：美日重疊圖。
- 2026-09-24 bridge v3.15／bot v1.23：備用模型換成 GLM 5.3 Flash。
- 2026-09-13 html v5.26–v5.29：基本面欄（P/E／EPS／Div／Growth／Sector），表格欄位合併、代碼欄 sticky。
- 2026-09-07 secreport.html（SEC 財報＋AI）；bridge v3.9–v3.11。
- 2026-08 起：Dealer Gamma 趨勢、K線 RSI／布林線、到期日曆、COT 週報、OPEX 提醒、雙 Barchart 帳戶。

（更早歷史見各檔案頁首 changelog。）
