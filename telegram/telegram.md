# Telegram GEX Bot 模組

> 最後更新：2026-10-02（Bot v1.24，持倉 17 隻）｜ 取代 2026-06-21 舊版
> 呢份係架構／備忘文件；實際行為以 `telegram_bot.py`（Project Files）頁首 changelog 為準。
> ⚠️ GitHub 上嘅 `telegram/telegram_bot.txt` 備份只係 **v1.9**，已嚴重過時——改 bot 前一律以 Project Files（v1.24）為 base，改完先更新 GitHub 備份。

---

## 📁 檔案清單

| 檔案 | GitHub 位置 | 用途 |
|---|---|---|
| `telegram_bot.py` | `telegram/telegram_bot.txt`（`.txt`） | Bot 主程式（長期運行） |
| `github_gex_updater.py` | `telegram/github_gex_updater.txt`（`.txt`） | 每日 2 次抓 Finnhub 報價／新聞 + Barchart GEX → 寫 `stocks/*.md` |
| `cftc_cot_updater.py` | 無（本機） | 每週六抓 CFTC Leveraged Funds COT → 寫 `cot/*.md` |
| `test_openrouter.py` | `telegram/test_openrouter.py` | OpenRouter 連線診斷（debug 用） |

Python 檔交付時一律改 `.txt`（`.py` 下載會失敗），用戶本機改名。GitHub 版本全部係佔位 key（`YOUR_xxx`），**不可直接執行**；真 key 只喺本機 `C:\Users\Dell\Downloads\FUTU\telegram\`。

---

## 🏗️ 架構

```
Telegram 指令 / 背景 job
   ├─ 主：Futu Bridge（127.0.0.1:8888）/api/quote /gex /kline /options_calendar
   │       報價用 session-aware 欄位（pre/after/overnight/last_price）
   ├─ 備：Finnhub /quote；GitHub stocks/*.md（GEX 快照）
   ├─ COT：GitHub cot/{ES,NQ}_COT.md（6 小時緩存）
   └─ AI：OpenRouter → DeepSeek V4 Flash 0731（主）→ GLM 5.3 Flash（備）
```

---

## ⚙️ 必填設定

`telegram_bot.py`：`TELEGRAM_BOT_TOKEN`、`OPENROUTER_API_KEY`、`FINNHUB_KEY`
`github_gex_updater.py`：`FINNHUB_KEY`、`BARCHART_EMAIL/PASS`（帳戶1）、`BARCHART_EMAIL2/PASS2`（帳戶2）、`GITHUB_TOKEN`
`cftc_cot_updater.py`：`GITHUB_TOKEN`（可選 `CFTC_APP_TOKEN`）

---

## 📋 持倉與 Barchart 帳戶分配（17 隻）

- **BATCH1（帳戶1，9 隻，quota 18/20，剩約 1 隻緩衝）**：GOOGL、AVGO、NVDA、MRVL、TER、META、NOK、RDW、LEU
- **BATCH2（帳戶2，8 隻，quota 16/20，剩約 2 隻緩衝）**：OKLO、RKLB、PLTR、ISRG、LYTE、RR、VRT、SERV
- 新持倉加落 BATCH2 或開第三個帳戶，**唔好加落帳戶1**。兩帳戶之間有 `asyncio.sleep(3)`。
- 持倉數字以最新 Futu CSV 為準（2026-10-01：GOOGL 20@245.04、NVDA 20@189.0625、NOK 200@12.458、PLTR 12@127.304 等）。
- 已清倉：MU（2026-09-03）、LITE（2026-08）。

---

## 🤖 指令

| 指令 | 功能 |
|---|---|
| `/start` `/help` | 歡迎／說明（`/help` 顯示版本號），並登記 chat_id（自動推送必須） |
| `/gex SYM [period]` | 任何美股（唔限持倉）：K線圖（疊 MA9/20/60 + GEX 橫線）＋ GEX by Strike 圖 ＋ 數字 ＋ AI 分析；period：1/5/15/30/60/D/W/M，預設 D |
| `/cot [ES\|NQ]` | CFTC Leveraged Funds 淨倉（COT Index、WoW、近4週） |
| `/report` | 全部持倉摘要 |
| `/pnl` | 持倉盈虧明細 |
| `/alert SYM above/below 價` ／ `list` ／ `remove SYM` | 手動價格警報 |
| `/ask 問題` | 自由問 AI，結合持倉 GEX＋新聞上下文 |

## ⏰ 自動功能（JobQueue）

| Job | 頻率 | 說明 |
|---|---|---|
| `gex_refresh_job` | 每 30 分鐘 | 預熱全部持倉 Futu 即時 GEX；`max_workers=4`；成段阻塞邏輯經 `asyncio.to_thread` 執行；cache TTL 20 小時，並持久化到 `gex_live_cache.json` |
| `gex_alert_job` | 每 15 分鐘 | 現價距離 Call/Put Wall < 3% 觸發，**已突破／已跌穿**亦觸發；同一警報 1 小時冷卻（breach 狀態獨立冷卻 key） |
| `opex_reminder_job` | 每日 08:00 HKT | 未來 3 日內 Monthly／Quarterly OPEX 提醒（用 bridge `/api/options_calendar`） |
| `cot_reminder_job` | 週六 08:15 HKT | 推送最新 COT（排喺 `COT_Monitor_Weekly` 08:00 之後 15 分鐘）；同一 report_date 只推一次 |

休市日（週末／NYSE 假期）自動跳過 GEX 警報同預熱。

---

## 📝 重要技術備忘

- **方向判斷由 code 負責**：`compute_wall_status()`（位置關係）同 `compute_breakout_scenario(dealer_bias)`（突破後係加速定壓抑：Long Gamma＝壓抑、Short Gamma＝加速）預先計好先交畀 AI；AI 唔准自己計百分比或判斷方向（AVGO／PLTR 事件教訓）。`/gex` 同 `/ask` 兩條路徑都要用。
- **AI model**：主 `deepseek/deepseek-v4-flash-0731`，備 `z-ai/glm-5.3-flash`（v1.23 由 Kimi K2.5 換入）。OpenRouter 帳戶地區被封鎖 OpenAI／Anthropic／Google，所以唔可以用佢哋。`max_tokens=2000`＋`reasoning:{effort:low, exclude:true}`；content 為 None／空字串、403、逾時都會自動 fallback（reasoning token 食晒預算會令 content 變 None，之前出過「AI分析：None」）。
- **AI 文字用 `safe_reply_markdown()` 發送**：LLM 輸出嘅 Markdown 符號可能唔配對，Telegram 會 `Can't parse entities` 令指令卡死；先試 Markdown，失敗改純文字重發。
- **Session 偵測（owning trading day）**：週五 20:00 ET 後至週日 20:00 ET 前＝weekend（冇夜盤）；週日 20:00 ET 後＝週一夜盤。`detect_et_session()`／`is_nyse_trading_day()` 同前端、bridge 各自複製一份，假期表要三處同步。
- **報價新舊判斷**：休市時段（週末／假期）顯示「上一交易日收市數據」，唔當警告；只有交易日內 Finnhub 報價超過 15 分鐘先警告。
- **GEX 資料優先次序**：Futu 即時（`_gex_live_cache`）→ GitHub `.md` 快照。期權市場休市時 `option_valid` 會令 Futu GEX 攞唔到，所以 cache TTL 拉長到 20 小時並落磁碟，process 重啟都保留。
- **K線圖**需要 `pip install mplfinance pandas`；缺依賴時會喺 Telegram 同終端提示，唔會靜默。
- **Futu SDK 單一 connection**：唔好用太多 thread 同時撞（部分 request 會快速失敗），所以並行度限 4。
- **Windows 排程器**設為「只有使用者登入時才執行」（電腦無開機密碼）。
- **`telegram_bot.py` 唔會 auto-reload**：改完要 Ctrl+C 重啟。
- **安裝**：`pip install "python-telegram-bot[job-queue]" requests matplotlib mplfinance`

---

## 🔗 相關連結

- 持倉儀表板：https://netng888-code.github.io/netng888/
- GEX 快照索引：[stocks/README.md](../stocks/README.md)
- 系統總文件：[DASHBOARD_CHANGELOG.md](../DASHBOARD_CHANGELOG.md)
- GitHub repo：https://github.com/netng888-code/netng888
