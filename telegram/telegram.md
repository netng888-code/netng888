# Telegram GEX Bot 模組

> 本資料夾包含 GEX 持倉監控系統嘅 Telegram Bot 相關代碼。
> 最後更新：2026-06-21（雙Barchart帳戶架構 + 持倉擴展至18隻）

---

## 📁 檔案清單

| 檔案 | 用途 |
|------|------|
| `github_gex_updater.py` | 每日抓取 Barchart GEX（雙帳戶分批，共18隻）+ Finnhub 報價/新聞，寫入 `stocks/*.md`（由 Windows 工作排程器 21:00 自動執行） |
| `telegram_bot.py` | Telegram Bot 主程式，讀取 `stocks/*.md` 數據，提供指令查詢 + AI分析 + 自動GEX警報（需長期運行） |
| `test_openrouter.py` | 獨立測試工具，快速診斷 OpenRouter API 連接問題（非日常使用，debug用） |

---

## 🏗️ 整體架構

```
github_gex_updater.py（21:00排程）
    ├── Finnhub 報價 + 新聞（ALL_HOLDINGS 全部18隻，無quota問題）
    ├── Barchart GEX 帳戶1（Playwright登入，BATCH1 首10大持倉）
    ├── Barchart GEX 帳戶2（Playwright登入，BATCH2 新增8隻，獨立帳戶分擔quota）
    └── 寫入 GitHub stocks/{TICKER}.md（共18檔）+ stocks/README.md 索引
            ↓
telegram_bot.py（長期運行）
    ├── 讀取 GitHub stocks/*.md（緩存GEX數據，ALL_HOLDINGS 全部18隻）
    ├── Finnhub 即時報價（覆蓋現價部分）
    ├── OpenRouter → DeepSeek（AI分析）
    └── 背景job：每15分鐘檢查持倉，逼近Call/Put Wall < 3% 自動推送警報
```

---

## ⚙️ 必填設定（每個檔案頂部）

### `github_gex_updater.py`
```python
FINNHUB_KEY     = "..."   # finnhub.io 免費申請
BARCHART_EMAIL  = "..."   # Barchart 帳戶1 email（負責 BATCH1，首10大持倉）
BARCHART_PASS   = "..."   # Barchart 帳戶1 密碼
BARCHART_EMAIL2 = "..."   # Barchart 帳戶2 email（負責 BATCH2，新增8隻持倉）
BARCHART_PASS2  = "..."   # Barchart 帳戶2 密碼
GITHUB_TOKEN    = "..."   # GitHub Personal Access Token (classic, repo權限)
```

### `telegram_bot.py`
```python
TELEGRAM_BOT_TOKEN = "..."   # BotFather 申請（@BotFather）
OPENROUTER_API_KEY = "..."   # openrouter.ai 申請
FINNHUB_KEY         = "..."   # 同上
```

### `test_openrouter.py`
```python
OPENROUTER_API_KEY = "..."   # 同上，純測試用
```

⚠️ **此GitHub版本已移除所有真實key（佔位字 `YOUR_xxx`），純粹備份/版本記錄用途，不可直接執行。**
本機（桌面）保留已填key嘅可執行版本。

---

## 📋 持倉清單與帳戶分配（2026-06-21，共18隻）

**BATCH1（Barchart帳戶1，10隻，quota用滿20/20）：**
MU、GOOGL、AVGO、NVDA、MRVL、TER、META、NOK、RDW、LEU

**BATCH2（Barchart帳戶2 `agent20268964@proton.me`，8隻，quota用16/20）：**
OKLO、RKLB、PLTR、ISRG、LITE、VRT、RR、SERV

> 兩個list合併成 `ALL_HOLDINGS`，供報價/新聞/`telegram_bot.py`使用；GEX抓取分開行（見上面架構圖）。

---

## 📦 安裝依賴

```bash
pip install playwright finnhub-python requests
pip install "python-telegram-bot[job-queue]"
playwright install chromium
```

---

## ▶️ 執行方法

### `github_gex_updater.py`
```bash
python github_gex_updater.py
```
通常由 **Windows 工作排程器**（任務名 `GEX_Monitor_Daily`）每日 21:00 自動執行，毋須手動跑。

### `telegram_bot.py`
```bash
python telegram_bot.py
```
⚠️ 需長期運行（保持 cmd 視窗開住），關閉視窗即代表 Bot 離線。

### `test_openrouter.py`
```bash
python test_openrouter.py
```
僅在 AI分析功能報錯時用嚎排查，平日不需要執行。

---

## 🤖 Telegram Bot 指令清單

| 指令 | 功能 |
|------|------|
| `/start` | 啟動歡迎訊息，登記chat_id（自動警報必須） |
| `/help` | 顯示指令說明 |
| `/gex TICKER` | 查單隻持倉GEX數據 + 即時報價 + AI分析 |
| `/report` | 今日全部18大持倉摘要 |
| `/pnl` | 計算持倉總盈虧明細 |
| `/alert TICKER above/below 價格` | 設定手動價格警報 |
| `/alert list` | 列出已設定嘅手動警報 |
| `/alert remove TICKER` | 移除手動警報 |

**自動GEX警報**（無需設定，已內置）：背景每15分鐘檢查全部持倉，現價距離Call/Put Wall < 3% 時主動推送，同一警報1小時內不重複發送。

---

## 📝 重要技術備忘

- **AI分析model**：原計劃用 Anthropic Claude，但因 OpenRouter 帳戶所屬地區（billing address）被封鎖存取 OpenAI / Anthropic / Google 三大provider，已改用 **DeepSeek**（`deepseek/deepseek-chat`），不受此地區限制，財務分析質素穩定。
- **報價新舊判斷**：Finnhub免費版 `/quote` 在市場休市時可能仍回傳上次收市價。`telegram_bot.py` 已加入 timestamp 判斷（超過15分鐘視為非即時），避免誤標「盤前/盤後」標籤，並在AI prompt中明確警告非即時報價，避免AI誤判市況。
- **Barchart 免費帳號 quota（2026-06-21雙帳戶架構）**：每個免費帳戶每日限20 page views，原本10隻持倉剛好用盡。持倉擴展到18隻後，開咗第二個Barchart帳戶（`agent20268964@proton.me`）分擔：
  - 帳戶1（`BARCHART_EMAIL`/`BARCHART_PASS`）→ `BATCH1` 首10大持倉 → 用滿20 view，**零緩衝**，唔好再加持倉落呢個帳戶
  - 帳戶2（`BARCHART_EMAIL2`/`BARCHART_PASS2`）→ `BATCH2` 新增8隻 → 用16 view，剩約2隻緩衝
  - 實測2026-06-21：兩帳戶獨立計quota，18/18隻GEX全部成功
  - 之後再加持倉，應加落帳戶2或開第三個帳戶，不可加落帳戶1
  - `github_gex_updater.py` 內 `fetch_all_gex()` 兩個帳戶之間有 `asyncio.sleep(3)` 間隔，避免太似自動化
- **報價/新聞不受Barchart quota限制**：`get_finnhub_quotes()` / `get_news()` 用 `ALL_HOLDINGS`（全部18隻）跑，Finnhub free tier係per-minute rate limit（60 calls/分鐘）唔係daily quota，所以唔受影響。
- **Windows 任務排程器**：設定為「只有使用者登入時才執行」（因電腦無開機密碼，無法使用「不論登入與否」選項）。
- **已知命名殘留（2026-06-21已修正）**：`generate_md()` 生成嘅 `.md` footer之前寫住舊script名 `morning_monitor.py`（疑似改名前遺留），已改正為 `github_gex_updater.py`。
- **`telegram_bot.py` 唔會自動reload**：佢係長期running嘅process，本機改完script檔案後，必須手動Ctrl+C再重啟先會讀到新嘅 `ALL_HOLDINGS` 清單／新邏輯。

---

## 🔗 相關連結

- 持倉儀表板：https://netng888-code.github.io/netng888/
- GEX快照索引：[stocks/README.md](../stocks/README.md)
- GitHub repo：https://github.com/netng888-code/netng888
