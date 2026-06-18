# Telegram GEX Bot 模組

> 本資料夾包含 GEX 持倉監控系統嘅 Telegram Bot 相關代碼。
> 最後更新：2026-06-18

---

## 📁 檔案清單

| 檔案 | 用途 |
|------|------|
| `github_gex_updater.py` | 每日抓取 Barchart GEX + Finnhub 報價/新聞，寫入 `stocks/*.md`（由 Windows 工作排程器 21:00 自動執行） |
| `telegram_bot.py` | Telegram Bot 主程式，讀取 `stocks/*.md` 數據，提供指令查詢 + AI分析 + 自動GEX警報（需長期運行） |
| `test_openrouter.py` | 獨立測試工具，快速診斷 OpenRouter API 連接問題（非日常使用，debug用） |

---

## 🏗️ 整體架構

```
github_gex_updater.py（21:00排程）
    ├── Barchart GEX（Playwright，已登入）
    ├── Finnhub 報價 + 新聞
    └── 寫入 GitHub stocks/{TICKER}.md
            ↓
telegram_bot.py（長期運行）
    ├── 讀取 GitHub stocks/*.md（緩存GEX數據）
    ├── Finnhub 即時報價（覆蓋現價部分）
    ├── OpenRouter → DeepSeek（AI分析）
    └── 背景job：每15分鐘檢查持倉，逼近Call/Put Wall < 3% 自動推送警報
```

---

## ⚙️ 必填設定（每個檔案頂部）

### `github_gex_updater.py`
```python
FINNHUB_KEY     = "..."   # finnhub.io 免費申請
BARCHART_EMAIL  = "..."   # Barchart 帳戶 email
BARCHART_PASS   = "..."   # Barchart 帳戶密碼
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
| `/report` | 今日全部10大持倉摘要 |
| `/pnl` | 計算持倉總盈虧明細 |
| `/alert TICKER above/below 價格` | 設定手動價格警報 |
| `/alert list` | 列出已設定嘅手動警報 |
| `/alert remove TICKER` | 移除手動警報 |

**自動GEX警報**（無需設定，已內置）：背景每15分鐘檢查全部持倉，現價距離Call/Put Wall < 3% 時主動推送，同一警報1小時內不重複發送。

---

## 📝 重要技術備忘

- **AI分析model**：原計劃用 Anthropic Claude，但因 OpenRouter 帳戶所屬地區（billing address）被封鎖存取 OpenAI / Anthropic / Google 三大provider，已改用 **DeepSeek**（`deepseek/deepseek-chat`），不受此地區限制，財務分析質素穩定。
- **報價新舊判斷**：Finnhub免費版 `/quote` 在市場休市時可能仍回傳上次收市價。`telegram_bot.py` 已加入 timestamp 判斷（超過15分鐘視為非即時），避免誤標「盤前/盤後」標籤，並在AI prompt中明確警告非即時報價，避免AI誤判市況。
- **Barchart 免費帳號**：每日限 20 page views，10隻持倉剛好用盡，不可頻繁重跑。
- **Windows 任務排程器**：設定為「只有使用者登入時才執行」（因電腦無開機密碼，無法使用「不論登入與否」選項）。

---

## 🔗 相關連結

- 持倉儀表板：https://netng888-code.github.io/netng888/
- GEX快照索引：[stocks/README.md](../stocks/README.md)
- GitHub repo：https://github.com/netng888-code/netng888
