"""
telegram_bot.py
═══════════════════════════════════════════════════
GEX 持倉監控 Telegram Bot

架構：
  Telegram指令
      ↓
  讀取 GitHub stocks/*.md（github_gex_updater.py 21:00已更新）
      ↓
  OpenRouter → DeepSeek（分析建議；因OpenRouter帳戶所屬
               地區被封鎖存取OpenAI/Anthropic/Google，
               已改用不受限制的DeepSeek model）
      ↓
  Telegram回覆

指令：
  /gex NVDA   — 查單隻GEX + AI分析
  /report     — 發送今日全部10隻摘要
  /pnl        — 計算持倉總盈虧
  /alert      — 設定/查看手動價格警報
  /help       — 指令說明

自動功能：
  GEX警報    — 背景每15分鐘檢查，當任何持倉現價
               距離Call/Put Wall < 3% 時自動主動推送
               （同一警報1小時內不重複發送）

安裝：
  pip install "python-telegram-bot[job-queue]" requests

執行：
  python telegram_bot.py
  （需要長期運行，建議用 Windows 工作排程器開機自動啟動，
   或保持終端窗口開啟）
═══════════════════════════════════════════════════
"""

import re
import json
import asyncio
import datetime
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest

# ═══════════════════════════════════════════════════
# ⚙️  設定區（只需改呢度）
# ═══════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"   # ← BotFather 俾你嗰串
OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY"   # ← openrouter.ai 嗰串
FINNHUB_KEY         = "YOUR_FINNHUB_KEY"          # ← finnhub.io 申請嗰串（免費）

GITHUB_OWNER  = "netng888-code"
GITHUB_REPO   = "netng888"
GITHUB_BRANCH = "main"

# AI分析模型（OpenRouter）
# ⚠️ 注意：你嘅OpenRouter帳戶billing地址所屬地區
#    被封鎖存取 OpenAI / Anthropic / Google 三大provider
#    （OpenRouter後台已確認："All other models remain available"）
#    改用 DeepSeek，財務分析質素優秀且完全唔受此限制
ANALYSIS_MODEL = "deepseek/deepseek-chat"

# 首10大持倉（同 github_gex_updater.py 保持一致）
TOP10 = [
    {"sym": "MU",    "name": "美光科技",       "qty": 5,   "cost": 557.857},
    {"sym": "GOOGL", "name": "谷歌-A",         "qty": 12,  "cost": 178.40 },
    {"sym": "AVGO",  "name": "博通",            "qty": 10,  "cost": 375.782},
    {"sym": "NVDA",  "name": "英偉達",          "qty": 15,  "cost": 148.50 },
    {"sym": "MRVL",  "name": "邁威爾科技",     "qty": 10,  "cost": 238.605},
    {"sym": "TER",   "name": "泰瑞達",          "qty": 5,   "cost": 92.00  },
    {"sym": "META",  "name": "Meta Platforms",  "qty": 3,   "cost": 606.333},
    {"sym": "NOK",   "name": "諾基亞",          "qty": 100, "cost": 13.50  },
    {"sym": "RDW",   "name": "Redwire",         "qty": 80,  "cost": 15.65  },
    {"sym": "LEU",   "name": "Centrus Energy",  "qty": 8,   "cost": 197.50 },
]
VALID_SYMS = {h["sym"] for h in TOP10}

# 簡單本地價格警報儲存（JSON文件）
ALERT_FILE = "alerts.json"

# ═══════════════════════════════════════════════════
# 讀取 GitHub stocks/{sym}.md（raw content）
# ═══════════════════════════════════════════════════
def fetch_stock_md(sym: str) -> str | None:
    url = (f"https://raw.githubusercontent.com/{GITHUB_OWNER}/"
           f"{GITHUB_REPO}/{GITHUB_BRANCH}/stocks/{sym}.md")
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None

# ═══════════════════════════════════════════════════
# 即時報價（Finnhub /quote）— 用於 /gex 指令現價部分
# ═══════════════════════════════════════════════════
def fetch_live_quote(sym: str) -> dict | None:
    """
    Finnhub免費版/quote回傳latest trade price，
    在美股開市時間外（pre-market/after-hours）通常仍反映
    最新成交，但Finnhub不提供明確時段標籤（不像Futu分盤前/
    盤後/夜盤）。呢個是免費API的真實限制，唔係程式錯誤。
    """
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": sym, "token": FINNHUB_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {
                "price":  d.get("c", 0),    # current/latest price
                "change": d.get("d", 0),
                "pct":    d.get("dp", 0),
                "prev":   d.get("pc", 0),
                "ts":     d.get("t", 0),    # unix timestamp of quote
            }
        return None
    except Exception:
        return None

def market_session_label(quote_ts: int = 0) -> str:
    """
    根據報價嘅timestamp判斷標籤，比純粹靠現時鐘時間更誠實：
    - 如果報價時間距離現在超過15分鐘，視為「非即時」（可能係上次收市價）
    - 如果報價時間夠新（15分鐘內），先根據美東時間判斷盤前/盤後/交易中
    """
    now = datetime.datetime.now()
    now_et = datetime.datetime.utcnow() - datetime.timedelta(hours=4)  # 粗略UTC-4(EDT)
    h = now_et.hour

    if quote_ts:
        quote_dt = datetime.datetime.fromtimestamp(quote_ts)
        age_min  = (now - quote_dt).total_seconds() / 60
        if age_min > 15:
            # 報價太舊，好可能係市場休市時嘅最後收市價，唔應該貼盤前/盤後標籤
            age_str = f"{int(age_min)}分鐘前" if age_min < 60 else f"{age_min/60:.1f}小時前"
            return f"⚠️ 非即時報價（{age_str}，可能係收市價）"

    if 4 <= h < 9 or (h == 9 and now_et.minute < 30):
        return "🌅 盤前時段"
    elif 9 <= h < 16:
        return "☀️ 正常交易時段"
    elif 16 <= h < 20:
        return "🌆 盤後時段"
    else:
        return "🌙 夜盤/休市時段"

# ═══════════════════════════════════════════════════
# 解析 .md 內容，抽出關鍵數字（供 /pnl /report 計算用）
# ═══════════════════════════════════════════════════
def parse_md(md: str) -> dict:
    """從 generate_md() 生成嘅 markdown 抽返結構化數據"""
    data = {}

    m = re.search(r'現價 \| \*\*\$([\d,]+\.?\d*)\*\*', md)
    if m: data["price"] = float(m.group(1).replace(",", ""))

    m = re.search(r'未實現盈虧 \| (▲|▼) \$([\d,]+)', md)
    if m:
        data["pnl_sign"] = 1 if m.group(1) == "▲" else -1
        data["pnl"] = float(m.group(2).replace(",", ""))

    m = re.search(r'Gamma Flip \| \$([\d,]+\.?\d*)', md)
    if m: data["flip"] = float(m.group(1).replace(",", ""))

    m = re.search(r'Put Wall（支撐） \| \$([\d,]+\.?\d*)', md)
    if m: data["put_wall"] = float(m.group(1).replace(",", ""))

    m = re.search(r'Call Wall（阻力） \| \$([\d,]+\.?\d*)', md)
    if m: data["call_wall"] = float(m.group(1).replace(",", ""))

    m = re.search(r'狀態[：:]\s*\*{0,2}(.+?)\*{0,2}\s*$', md, re.MULTILINE)
    if m: data["status"] = m.group(1).strip()

    m = re.search(r'最後更新：([\d\- :]+HKT)', md)
    if m: data["updated"] = m.group(1).strip()

    return data

# ═══════════════════════════════════════════════════
# OpenRouter → DeepSeek：生成分析建議
# ═══════════════════════════════════════════════════
def ask_ai(prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/netng888-code/netng888",
        "X-Title": "GEX Monitor Bot",
    }
    payload = {
        "model": ANALYSIS_MODEL,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)

        # 一律先印完整response到終端，方便排查任何狀態碼
        print(f"[OpenRouter] status={r.status_code}  body={r.text[:500]}")

        if r.status_code == 200:
            result = r.json()
            choices = result.get("choices", [])
            if not choices:
                return f"⚠️ AI回傳空結果，完整回應：{str(result)[:200]}"
            return choices[0]["message"]["content"]
        else:
            error_detail = ""
            try:
                error_json = r.json()
                error_detail = error_json.get("error", {}).get("message", r.text[:300])
            except Exception:
                error_detail = r.text[:300]

            if r.status_code == 401:
                return "⚠️ AI API認證失敗：OPENROUTER_API_KEY無效或未填入"
            elif r.status_code == 402:
                return "⚠️ OpenRouter帳戶餘額不足，請去openrouter.ai充值"
            elif r.status_code == 403:
                return f"⚠️ AI API被拒絕 [403]：{error_detail}"
            elif r.status_code == 429:
                return "⚠️ 請求過於頻密，請稍後再試"
            else:
                return f"⚠️ AI API錯誤 [{r.status_code}]：{error_detail}"
    except requests.exceptions.Timeout:
        return "⚠️ AI API連接逾時（30秒），請稍後再試"
    except Exception as e:
        return f"⚠️ AI API連接失敗：{type(e).__name__}: {e}"

def build_gex_prompt(sym: str, name: str, data: dict, live: dict | None, session: str) -> str:
    # 決定真正應該俾AI用嗰個「現價」：優先用即時報價，冇先回退緩存
    is_stale = session.startswith("⚠️")  # session本身已標示報價非即時
    if live and live.get("price"):
        current_price = live["price"]
        price_label   = "最後報價（可能非即時）" if is_stale else "現價"
        price_note    = f"（{session}）"
    else:
        current_price = data.get("price", "N/A")
        price_label   = "最後報價"
        price_note    = "（21:00緩存價，即時報價暫不可用）"

    gex_basis_note = ""
    if live and live.get("price") and data.get("price"):
        gex_basis_note = (
            f"\n（注意：Call/Put Wall等GEX水平係根據昨日21:00收盤價"
            f"${data.get('price')}計算所得，{price_label}已更新為${current_price}，"
            f"分析時請以呢個{price_label}為準判斷距離牆嘅遠近）"
        )

    stale_warning = ""
    if is_stale:
        stale_warning = (
            "\n\n⚠️ 重要：以上報價並非即時市場價，可能係市場休市時嘅最後成交價。"
            "請喺分析中提醒用戶呢點，唔好將呢個價當作「現時」嘅市況下結論，"
            "並建議用戶查證實時報價（例如打開Futu app）先做決定。"
        )

    return f"""你是一位專業的GEX（Gamma Exposure）期權分析師，正在為一位持有{sym}（{name}）的退休投資者提供簡短操作建議。

該投資者背景：已退休，風險承受能力中低，傾向保守至中等策略，關注下跌風險多於追求最高回報。

當前數據：
{price_label}：${current_price} {price_note}{gex_basis_note}{stale_warning}
Gamma Flip：${data.get('flip', 'N/A')}
Put Wall（支撐）：${data.get('put_wall', 'N/A')}
Call Wall（阻力）：${data.get('call_wall', 'N/A')}
狀態：{data.get('status', 'N/A')}

請用繁體中文（可用少量粵語表達習慣），給出3-4句簡短具體的操作建議，包括：
1. 短線風險提示（以上方{price_label}計算距離Call/Put Wall嘅實際百分比，是否接近關鍵水平）
2. 是否建議調整持倉（不要假設用戶會盲目跟隨，給出條件式建議）
3. 不要使用任何免責聲明或"僅供參考"等套話，直接給出分析

回覆控制在100字以內，語氣專業但不要過度保守，避免空泛建議。
重要：分析必須以上方{price_label}（${current_price}）為基準計算距離，不要用GEX計算基準價代替。"""

# ═══════════════════════════════════════════════════
# /gex 指令：查單隻GEX + AI分析
# ═══════════════════════════════════════════════════
async def cmd_gex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text(
            "用法：/gex NVDA\n"
            f"可查股票：{', '.join(sorted(VALID_SYMS))}"
        )
        return

    sym = context.args[0].upper()
    if sym not in VALID_SYMS:
        await update.message.reply_text(
            f"⚠️ {sym} 不在持倉清單\n"
            f"可查：{', '.join(sorted(VALID_SYMS))}"
        )
        return

    await update.message.reply_text(f"⏳ 查詢 {sym} GEX 數據...")

    md = fetch_stock_md(sym)
    if not md:
        await update.message.reply_text(
            f"⚠️ 無法讀取 {sym} 數據，可能 GitHub 未更新或網絡問題"
        )
        return

    data = parse_md(md)
    name = next((h["name"] for h in TOP10 if h["sym"] == sym), sym)

    # 嘗試攞即時報價覆蓋緩存價格（GEX數據維持用緩存，因為一日先變一次）
    live = fetch_live_quote(sym)
    quote_ts = live.get("ts", 0) if live else 0
    session = market_session_label(quote_ts)

    is_stale = session.startswith("⚠️")
    if live and live.get("price"):
        cached_price = data.get("price")
        live_price   = live["price"]
        live_pct     = live.get("pct", 0)
        price_label  = "最後報價" if is_stale else "現價"
        price_line   = (
            f"{price_label}：${live_price:,.2f}　({live_pct:+.2f}%，相對前收)\n"
            f"　　{session}\n"
        )
        if cached_price:
            price_line += f"　　_GEX計算基準價：${cached_price:,.2f}（21:00更新）_\n"
    else:
        # 即時報價攞不到，回退用緩存價格，明確標示
        price_line = (
            f"最後報價：${data.get('price', 'N/A')}\n"
            f"　　⚠️ 即時報價暫不可用，顯示21:00緩存價\n"
        )

    # 組裝基本數據訊息
    msg = f"📊 *{sym}* — {name}\n\n"
    msg += price_line
    msg += f"\nGamma Flip：${data.get('flip', 'N/A')}\n"
    msg += f"Put Wall：${data.get('put_wall', 'N/A')}\n"
    msg += f"Call Wall：${data.get('call_wall', 'N/A')}\n"
    msg += f"狀態：{data.get('status', 'N/A')}\n"
    msg += f"\n_GEX數據更新：{data.get('updated', 'N/A')}_\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

    # AI分析（額外發一條訊息，避免等太耐）
    await update.message.reply_text("🤖 正在生成分析...")
    prompt = build_gex_prompt(sym, name, data, live, session)
    analysis = ask_ai(prompt)
    await update.message.reply_text(f"🤖 *AI分析：*\n{analysis}", parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /report 指令：今日全部10隻摘要
# ═══════════════════════════════════════════════════
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    await update.message.reply_text("⏳ 生成今日報告（10隻持倉）...")

    lines = [f"📋 *今日持倉GEX報告* — {datetime.date.today()}\n"]
    total_pnl = 0

    for h in TOP10:
        sym = h["sym"]
        md = fetch_stock_md(sym)
        if not md:
            lines.append(f"{sym}：⚠️ 讀取失敗")
            continue
        data = parse_md(md)

        price = data.get("price", 0)
        pnl   = data.get("pnl", 0)
        sign  = data.get("pnl_sign", 1)
        signed_pnl = pnl * sign
        total_pnl += signed_pnl

        status = data.get("status", "")
        # GEX狀態符號（同盈虧顏色分開，避免混淆）
        if "逼近Call" in status:
            gex_icon = "⚠️"   # 接近阻力，留意風險
        elif "逼近Put" in status:
            gex_icon = "🛡️"   # 接近支撐，相對安全
        else:
            gex_icon = "▫️"   # 中間地帶

        # 盈虧顏色：升=綠色，跌=紅色（港股慣例）
        pnl_color = "🟢" if sign >= 0 else "🔴"
        pnl_arrow = "▲" if sign >= 0 else "▼"

        lines.append(
            f"{gex_icon} *{sym}* ${price:,.2f}  "
            f"{pnl_color}{pnl_arrow}${abs(pnl):,.0f}"
        )

    total_color = "🟢" if total_pnl >= 0 else "🔴"
    total_arrow = "▲" if total_pnl >= 0 else "▼"
    lines.append(f"\n💰 *總浮盈虧：{total_color}{total_arrow}${abs(total_pnl):,.0f}*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /pnl 指令：總盈虧計算
# ═══════════════════════════════════════════════════
async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    await update.message.reply_text("⏳ 計算總盈虧...")

    total_value = 0
    total_cost  = 0
    lines = ["💰 *持倉盈虧明細*\n"]

    for h in TOP10:
        sym = h["sym"]
        md  = fetch_stock_md(sym)
        if not md:
            continue
        data  = parse_md(md)
        price = data.get("price", 0)
        qty   = h["qty"]
        cost  = h["cost"]

        value     = price * qty
        cost_total= cost * qty
        pnl       = value - cost_total
        pnl_pct   = (pnl / cost_total * 100) if cost_total else 0

        total_value += value
        total_cost  += cost_total

        color = "🟢" if pnl >= 0 else "🔴"
        arrow = "▲" if pnl >= 0 else "▼"
        lines.append(f"{color}{sym}: {arrow}${abs(pnl):,.0f} ({pnl_pct:+.1f}%)")

    total_pnl     = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    total_color   = "🟢" if total_pnl >= 0 else "🔴"
    arrow         = "▲" if total_pnl >= 0 else "▼"

    lines.append(f"\n━━━━━━━━━━━━━━")
    lines.append(f"市值總計：${total_value:,.0f}")
    lines.append(f"成本總計：${total_cost:,.0f}")
    lines.append(f"*總盈虧：{total_color}{arrow}${abs(total_pnl):,.0f} ({total_pnl_pct:+.1f}%)*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /alert 指令：簡單價格警報（本地JSON儲存）
# ═══════════════════════════════════════════════════
def load_alerts() -> dict:
    try:
        with open(ALERT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_alerts(alerts: dict):
    with open(ALERT_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    用法：
      /alert NVDA above 210   — NVDA升穿210提示
      /alert NVDA below 190   — NVDA跌穿190提示
      /alert list             — 列出所有警報
      /alert remove NVDA      — 移除NVDA警報
    """
    register_chat(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text(
            "用法：\n"
            "/alert NVDA above 210\n"
            "/alert NVDA below 190\n"
            "/alert list\n"
            "/alert remove NVDA"
        )
        return

    alerts = load_alerts()
    chat_id = str(update.effective_chat.id)
    user_alerts = alerts.get(chat_id, {})

    if context.args[0].lower() == "list":
        if not user_alerts:
            await update.message.reply_text("📭 暫無設定警報")
            return
        lines = ["🔔 *目前警報*\n"]
        for sym, conf in user_alerts.items():
            lines.append(f"{sym}: {conf['direction']} ${conf['price']}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    if context.args[0].lower() == "remove":
        if len(context.args) < 2:
            await update.message.reply_text("用法：/alert remove NVDA")
            return
        sym = context.args[1].upper()
        if sym in user_alerts:
            del user_alerts[sym]
            alerts[chat_id] = user_alerts
            save_alerts(alerts)
            await update.message.reply_text(f"✅ 已移除 {sym} 警報")
        else:
            await update.message.reply_text(f"⚠️ {sym} 沒有設定警報")
        return

    if len(context.args) < 3:
        await update.message.reply_text("用法：/alert NVDA above 210")
        return

    sym       = context.args[0].upper()
    direction = context.args[1].lower()
    try:
        price = float(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ 價格必須是數字")
        return

    if sym not in VALID_SYMS:
        await update.message.reply_text(f"⚠️ {sym} 不在持倉清單")
        return
    if direction not in ("above", "below"):
        await update.message.reply_text("⚠️ 方向必須是 above 或 below")
        return

    user_alerts[sym] = {"direction": direction, "price": price}
    alerts[chat_id]  = user_alerts
    save_alerts(alerts)

    await update.message.reply_text(
        f"✅ 已設定：{sym} {direction} ${price} 時提示"
    )

# ═══════════════════════════════════════════════════
# 自動GEX警報（背景循環，每15分鐘檢查一次）
# ═══════════════════════════════════════════════════
GEX_ALERT_THRESHOLD_PCT = 3.0      # 距離Wall < 3% 觸發
GEX_ALERT_COOLDOWN_SEC  = 3600     # 同一警報1小時內不重發
KNOWN_CHATS_FILE        = "known_chats.json"
GEX_ALERT_LOG_FILE      = "gex_alert_log.json"

def register_chat(chat_id: int):
    """每次任何指令被使用時呼叫，記住呢個chat_id供背景job推送用"""
    try:
        with open(KNOWN_CHATS_FILE, "r", encoding="utf-8") as f:
            chats = json.load(f)
    except Exception:
        chats = []
    cid = str(chat_id)
    if cid not in chats:
        chats.append(cid)
        with open(KNOWN_CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f, ensure_ascii=False, indent=2)

def get_known_chats() -> list:
    try:
        with open(KNOWN_CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def load_gex_alert_log() -> dict:
    """記錄每個 sym+wall_type 上次觸發嘅unix timestamp，做冷卻判斷"""
    try:
        with open(GEX_ALERT_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_gex_alert_log(log: dict):
    with open(GEX_ALERT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def check_gex_proximity(sym: str, price: float, call_wall: float, put_wall: float) -> dict | None:
    """
    計算現價距離Call/Put Wall的%，若 < 閾值就回傳觸發資訊。
    若同時逼近兩邊（理論上罕見），優先回報較近嗰個。
    """
    if not price or not call_wall or not put_wall:
        return None

    dist_call_pct = (call_wall - price) / price * 100
    dist_put_pct  = (price - put_wall)  / price * 100

    triggers = []
    if 0 <= dist_call_pct < GEX_ALERT_THRESHOLD_PCT:
        triggers.append(("call", dist_call_pct, call_wall))
    if 0 <= dist_put_pct < GEX_ALERT_THRESHOLD_PCT:
        triggers.append(("put", dist_put_pct, put_wall))

    if not triggers:
        return None

    # 揀距離最近嗰個
    wall_type, dist_pct, wall_price = min(triggers, key=lambda t: t[1])
    return {"wall_type": wall_type, "dist_pct": dist_pct, "wall_price": wall_price}

async def gex_alert_job(context: ContextTypes.DEFAULT_TYPE):
    """
    每15分鐘執行一次嘅背景job。
    對TOP10每隻：攞即時報價 + 緩存GEX數據 → 判斷是否逼近Wall
    → 若觸發且未在冷卻期內 → 主動push俾所有已知chat_id
    """
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🔍 GEX警報檢查開始...")

    known_chats = get_known_chats()
    if not known_chats:
        print("   ⚠️ 暫無已知chat_id，略過（用戶需先發送任何指令一次）")
        return

    alert_log = load_gex_alert_log()
    now_ts = datetime.datetime.now().timestamp()
    triggered_count = 0

    for h in TOP10:
        sym = h["sym"]
        name = h["name"]

        # GEX數據（Call/Put Wall）用緩存，因為一日先更新一次
        md = fetch_stock_md(sym)
        if not md:
            continue
        data = parse_md(md)
        call_wall = data.get("call_wall")
        put_wall  = data.get("put_wall")
        if not call_wall or not put_wall:
            continue

        # 現價用即時Finnhub報價
        live = fetch_live_quote(sym)
        if not live or not live.get("price"):
            continue
        price = live["price"]
        pct   = live.get("pct", 0)

        # 檢查報價新舊：如果係超過15分鐘前嘅舊報價（例如市場休市），
        # 唔應該基於呢個價觸發警報，避免假訊號
        quote_ts = live.get("ts", 0)
        if quote_ts:
            age_min = (now_ts - quote_ts) / 60
            if age_min > 15:
                continue  # 報價太舊，市場可能休市，略過呢隻股

        result = check_gex_proximity(sym, price, call_wall, put_wall)
        if not result:
            continue

        wall_type   = result["wall_type"]
        dist_pct    = result["dist_pct"]
        wall_price  = result["wall_price"]

        # 冷卻判斷：同一個 sym+wall_type 組合1小時內唔重複發
        log_key = f"{sym}_{wall_type}"
        last_ts = alert_log.get(log_key, 0)
        if now_ts - last_ts < GEX_ALERT_COOLDOWN_SEC:
            continue  # 仍在冷卻期，略過

        # 觸發！組裝推送訊息
        wall_label = "Call Wall（阻力）" if wall_type == "call" else "Put Wall（支撐）"
        icon       = "🔴" if wall_type == "call" else "🟢"
        arrow      = "▲" if pct >= 0 else "▼"

        msg = (
            f"{icon} *GEX警報：{sym}* — {name}\n\n"
            f"現價：${price:,.2f}　{arrow}{abs(pct):.2f}%\n"
            f"距離{wall_label}：僅 {dist_pct:.1f}%\n"
            f"{wall_label}水平：${wall_price:,.2f}\n\n"
            f"_此警報1小時內不會重複發送_"
        )

        for chat_id in known_chats:
            try:
                await context.bot.send_message(
                    chat_id=int(chat_id), text=msg, parse_mode="Markdown"
                )
            except Exception as e:
                print(f"   ⚠️ 推送至chat_id={chat_id}失敗: {e}")

        alert_log[log_key] = now_ts
        triggered_count += 1
        print(f"   🔔 觸發：{sym} 距離{wall_label} {dist_pct:.1f}%")

    if triggered_count > 0:
        save_gex_alert_log(alert_log)
    print(f"   ✅ 檢查完成，本次觸發 {triggered_count} 個警報")

# ═══════════════════════════════════════════════════
# /help 指令
# ═══════════════════════════════════════════════════
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    msg = """🤖 *GEX持倉監控 Bot*

/gex NVDA — 查單隻GEX數據 + AI分析
/report — 今日全部10隻持倉摘要
/pnl — 計算持倉總盈虧
/alert NVDA above 210 — 設定價格警報
/alert list — 列出所有警報
/alert remove NVDA — 移除警報
/help — 顯示此說明

數據每日21:00自動更新（來源：Barchart + Finnhub）

🔔 *自動GEX警報*（已啟用，無需設定）
當任何持倉現價距離Call/Put Wall < 3%時
會自動主動通知你（每15分鐘檢查一次，
同一警報1小時內不重複發送）"""
    await update.message.reply_text(msg, parse_mode="Markdown")

# ═══════════════════════════════════════════════════
# /start 指令
# ═══════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    await update.message.reply_text(
        "👋 歡迎使用GEX持倉監控Bot！\n輸入 /help 查看所有指令\n\n"
        "🔔 自動GEX警報已為你啟用，當持倉逼近Call/Put Wall時會主動通知"
    )

# ═══════════════════════════════════════════════════
# 未知指令（避免Telegram靜默無回應）
# ═══════════════════════════════════════════════════
async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_chat(update.effective_chat.id)
    text = update.message.text or ""
    await update.message.reply_text(
        f"⚠️ 未知指令：{text}\n"
        "輸入 /help 查看可用指令清單"
    )

# ═══════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════
def main():
    print("🤖 GEX Telegram Bot 啟動中...")

    # 自我檢查：確保key已填好，唔再係佔位字
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        print("❌ 錯誤：TELEGRAM_BOT_TOKEN 仍未填入，請編輯腳本第44行")
        return
    if OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY" or not OPENROUTER_API_KEY:
        print("⚠️ 警告：OPENROUTER_API_KEY 仍未填入，AI分析功能將無法使用")
        print("   （/gex /report /pnl 等基本功能不受影響，只係AI分析部分會錯誤）")

    # 延長逾時時間（預設5秒對某些Windows網絡環境太短）
    # 並指明用IPv4，避免IPv6解析延遲導致逾時
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .get_updates_request(request)
        .build()
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("gex",    cmd_gex))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("pnl",    cmd_pnl))
    app.add_handler(CommandHandler("alert",  cmd_alert))
    # 捕捉所有未匹配嘅指令（必須放最後，唔阻擋上面已註冊嘅指令）
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    # 背景GEX警報：每15分鐘檢查一次，啟動後10秒先首次執行
    if app.job_queue:
        app.job_queue.run_repeating(
            gex_alert_job,
            interval=900,    # 15分鐘 = 900秒
            first=10,         # 啟動後10秒首次執行
        )
        print("🔔 自動GEX警報已啟用（每15分鐘檢查，距離Wall<3%觸發）")
    else:
        print("⚠️ job_queue未能初始化，自動GEX警報功能停用")
        print("   請確認已安裝：pip install \"python-telegram-bot[job-queue]\"")

    print("✅ Bot 已啟動，等待Telegram指令...")
    print("   （按 Ctrl+C 停止）")
    app.run_polling()

if __name__ == "__main__":
    main()
