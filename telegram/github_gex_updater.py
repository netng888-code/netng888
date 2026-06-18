"""
github_gex_updater.py
═══════════════════════════════════════════════════
每日開盤前自動：
  1. 抓 Barchart GEX（Playwright）
  2. 抓 Finnhub 報價 + 新聞
  3. 生成 Markdown 內容
  4. 用 GitHub API 寫入 stocks/TICKER.md

安裝：
  pip install playwright finnhub-python requests
  playwright install chromium

執行：
  python github_gex_updater.py
═══════════════════════════════════════════════════
"""

import re, time, asyncio, datetime, base64
import json, requests, finnhub
from playwright.async_api import async_playwright

# ═══════════════════════════════════════════════════
# ⚙️  設定區（只需改呢度）
# ═══════════════════════════════════════════════════
FINNHUB_KEY     = "YOUR_FINNHUB_KEY"           # ← finnhub.io 申請嗰串（免費）
BARCHART_EMAIL  = "YOUR_BARCHART_EMAIL"        # ← 你嘅Barchart帳戶email
BARCHART_PASS   = "YOUR_BARCHART_PASSWORD"     # ← 填 Barchart 密碼

GITHUB_TOKEN    = "YOUR_GITHUB_TOKEN"          # ← 填 GitHub Personal Access Token
GITHUB_OWNER    = "netng888-code"
GITHUB_REPO     = "netng888"
GITHUB_BRANCH   = "main"

# 首10大持倉
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

# ═══════════════════════════════════════════════════
# GitHub API：讀取現有文件 SHA（更新必須提供）
# ═══════════════════════════════════════════════════
def get_file_sha(path: str) -> str | None:
    """取得文件現有 SHA，新文件返回 None"""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("sha")
    return None  # 文件不存在

# ═══════════════════════════════════════════════════
# GitHub API：寫入 / 更新文件
# ═══════════════════════════════════════════════════
def write_to_github(path: str, content: str, commit_msg: str) -> bool:
    """
    寫入文件到 GitHub repo
    path    : 例如 "stocks/MU.md"
    content : 文件內容（UTF-8 字串）
    """
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Base64 encode 內容
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": commit_msg,
        "content": encoded,
        "branch":  GITHUB_BRANCH,
    }

    # 如果文件已存在，需要提供 SHA
    sha = get_file_sha(path)
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    if r.status_code in (200, 201):
        return True
    else:
        print(f"    ❌ GitHub 寫入失敗 [{r.status_code}]: {r.text[:200]}")
        return False

# ═══════════════════════════════════════════════════
# 生成 Markdown 內容
# ═══════════════════════════════════════════════════
def generate_md(h: dict, quote: dict, gex: dict, news: list) -> str:
    sym   = h["sym"];  name  = h["name"]
    qty   = h["qty"];  cost  = h["cost"]
    price = quote.get("price", 0)
    chg   = quote.get("change", 0)
    pct   = quote.get("pct", 0)
    pnl   = (price - cost) * qty
    pnl_p = (price - cost) / cost * 100 if cost else 0

    flip      = gex.get("flip")
    put_wall  = gex.get("put_wall")
    call_wall = gex.get("call_wall")

    now       = datetime.datetime.now()
    date_str  = now.strftime("%Y-%m-%d")
    time_str  = now.strftime("%H:%M HKT")

    # 狀態判斷
    status = "❓ GEX 數據不足"
    dist_call_str = "—"
    dist_put_str  = "—"
    if call_wall and put_wall and price:
        dist_call = (call_wall - price) / price * 100
        dist_put  = (price - put_wall)  / price * 100
        dist_call_str = f"+{dist_call:.1f}%"
        dist_put_str  = f"-{dist_put:.1f}%"
        regime = "⚠️ 負Gamma區" if (flip and price < flip) else "✅ 正Gamma區"
        if dist_call < 1.5:
            zone = "🔴 逼近Call牆"
        elif dist_call < 3.0:
            zone = "🟡 接近Call牆"
        elif dist_put < 1.5:
            zone = "🟢 逼近Put牆支撐"
        else:
            zone = "🔵 中間地帶"
        status = f"{regime} {zone}"

    pnl_arrow = "▲" if pnl >= 0 else "▼"
    chg_arrow = "▲" if chg >= 0 else "▼"
    pct_sign  = "+" if pct >= 0 else ""

    # 新聞 Markdown：每條一個區塊 —— 標題(連結) + 摘要 + 來源/時間
    if news:
        blocks = []
        for n in news:
            headline = n.get("headline", "")
            summary  = n.get("summary", "")
            url      = n.get("url", "")
            src      = n.get("source", "")
            age      = n.get("age", "")

            # 標題：有連結就做成 Markdown 連結，冇就純文字
            if url:
                title_line = f"**[{headline}]({url})**"
            else:
                title_line = f"**{headline}**"

            meta_line = f"*{src} · {age}*" if (src or age) else ""

            block = title_line
            if meta_line:
                block += f"  \n{meta_line}"
            if summary:
                block += f"  \n{summary}"

            blocks.append(block)

        news_md = "\n\n".join([f"- {b}" for b in blocks])
    else:
        news_md = "- 暫無新聞"

    md = f"""# {sym} — {name}

> 最後更新：{date_str} {time_str}　｜　數據來源：Barchart GEX + Finnhub

---

## 📊 今日快照

| 項目 | 數值 |
|------|------|
| 現價 | **${price:,.2f}** |
| 今日變動 | {chg_arrow} ${abs(chg):.2f}　({pct_sign}{pct:.2f}%) |
| 持倉數量 | {qty} 股 |
| 平均成本 | ${cost:.3f} |
| 未實現盈虧 | {pnl_arrow} ${abs(pnl):,.0f}　({pnl_arrow}{abs(pnl_p):.1f}%) |

---

## 🎯 GEX 關鍵水平

| 指標 | 數值 | 距離現價 |
|------|------|---------|
| Gamma Flip | ${flip:,.2f} | — |
| Put Wall（支撐） | ${put_wall:,.2f} | {dist_put_str} |
| Call Wall（阻力） | ${call_wall:,.2f} | {dist_call_str} |

**狀態：{status}**

---

## 📰 最新新聞

{news_md}

---

## 📝 操作記錄

| 日期 | 動作 | 價格 | 數量 | 備註 |
|------|------|------|------|------|
| {date_str} | 監控 | ${price:,.2f} | — | 自動更新 |

---

## 🔗 參考連結

- [Barchart GEX](https://www.barchart.com/stocks/quotes/{sym}/gamma-exposure)
- [Finviz](https://finviz.com/quote.ashx?t={sym})
- [TradingView](https://www.tradingview.com/chart/?symbol={sym})

---
*由 morning_monitor.py 自動生成　{date_str} {time_str}*
"""
    return md

# ═══════════════════════════════════════════════════
# Finnhub：報價
# ═══════════════════════════════════════════════════
def get_finnhub_quotes(symbols: list) -> dict:
    client = finnhub.Client(api_key=FINNHUB_KEY)
    quotes = {}
    for sym in symbols:
        try:
            q = client.quote(sym)
            quotes[sym] = {
                "price":  q.get("c",  0),
                "change": q.get("d",  0),
                "pct":    q.get("dp", 0),
            }
            time.sleep(0.15)
        except:
            quotes[sym] = {"price": 0, "change": 0, "pct": 0}
    return quotes

# ═══════════════════════════════════════════════════
# Finnhub：新聞
# ═══════════════════════════════════════════════════
def get_news(sym: str) -> list:
    """
    回傳 dict list，每條包含：
      headline (完整標題，不截斷)
      summary  (摘要，最多2句)
      url      (原文連結)
      source, age_str
    """
    client = finnhub.Client(api_key=FINNHUB_KEY)
    try:
        today     = datetime.date.today()
        from_date = (today - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        to_date   = today.strftime("%Y-%m-%d")
        news      = client.company_news(sym, _from=from_date, to=to_date)
        out = []
        for item in news[:3]:
            headline = item.get("headline", "").strip()
            summary  = item.get("summary", "").strip()
            url      = item.get("url", "")
            src      = item.get("source", "")
            ts       = item.get("datetime", 0)

            age_str = ""
            if ts:
                dt    = datetime.datetime.fromtimestamp(ts)
                age_h = int((datetime.datetime.now() - dt).total_seconds() / 3600)
                age_str = f"{age_h}h前" if age_h < 24 else f"{age_h // 24}d前"

            # 摘要保留前160字（夠顯示1-2句），避免內容太長
            if summary:
                summary_short = (summary[:160] + "…") if len(summary) > 160 else summary
            else:
                summary_short = ""

            if headline:
                out.append({
                    "headline": headline,   # 完整標題，不截斷
                    "summary":  summary_short,
                    "url":      url,
                    "source":   src,
                    "age":      age_str,
                })
        return out
    except:
        return []

# ═══════════════════════════════════════════════════
# Barchart GEX（Playwright）
# ═══════════════════════════════════════════════════
async def barchart_login(page) -> bool:
    try:
        await page.goto("https://www.barchart.com/login",
                        wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        await page.fill('input[name="email"], input[type="email"]', BARCHART_EMAIL)
        await asyncio.sleep(0.5)
        await page.fill('input[name="password"], input[type="password"]', BARCHART_PASS)
        await asyncio.sleep(0.5)
        await page.click('button[type="submit"], input[type="submit"]')
        await asyncio.sleep(3)
        print("    ✅ Barchart 登入完成")
        return True
    except Exception as e:
        print(f"    ⚠️  登入問題: {e}")
        return False

async def fetch_one_gex(sym: str, page) -> dict:
    url    = f"https://www.barchart.com/stocks/quotes/{sym}/gamma-exposure"
    result = {"flip": None, "put_wall": None, "call_wall": None}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(3)
        text = await page.inner_text("body")
        m_flip  = re.search(r'gamma flip point is ([\d,]+\.?\d*)', text, re.I)
        m_put   = re.search(r'put wall is ([\d,]+\.?\d*)',          text, re.I)
        m_call  = re.search(r'call wall is ([\d,]+\.?\d*)',         text, re.I)
        if m_flip:  result["flip"]     = float(m_flip.group(1).replace(",", ""))
        if m_put:   result["put_wall"] = float(m_put.group(1).replace(",", ""))
        if m_call:  result["call_wall"]= float(m_call.group(1).replace(",", ""))
    except Exception as e:
        result["error"] = str(e)
    return result

async def fetch_all_gex(symbols: list) -> dict:
    gex_data = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx     = await browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ))
        page = await ctx.new_page()
        await barchart_login(page)
        await asyncio.sleep(2)

        for sym in symbols:
            print(f"    📡 {sym}...", end=" ", flush=True)
            data = await fetch_one_gex(sym, page)
            gex_data[sym] = data
            print("✅" if data.get("call_wall") else "⚠️")
            await asyncio.sleep(2)

        await browser.close()
    return gex_data

# ═══════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════
async def main():
    now     = datetime.datetime.now()
    symbols = [h["sym"] for h in TOP10]
    date_str = now.strftime("%Y-%m-%d")

    print(f"\n{'═'*60}")
    print(f"  📊 GEX Monitor → GitHub  {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*60}")

    # Step 1: 報價
    print("\n⏳ [1/4]  Finnhub 報價...")
    quotes = get_finnhub_quotes(symbols)
    print(f"  ✅ {len(quotes)} 隻")

    # Step 2: GEX
    print("\n⏳ [2/4]  Barchart GEX...")
    gex_all = await fetch_all_gex(symbols)
    ok = sum(1 for g in gex_all.values() if g.get("call_wall"))
    print(f"  ✅ {ok}/{len(symbols)} 隻 GEX 成功")

    # Step 3: 新聞
    print("\n⏳ [3/4]  Finnhub 新聞...")
    news_all = {sym: get_news(sym) for sym in symbols}
    print(f"  ✅ 完成")

    # Step 4: 寫入 GitHub
    print("\n⏳ [4/4]  寫入 GitHub stocks/*.md ...")
    success = 0
    for h in TOP10:
        sym = h["sym"]
        md  = generate_md(
            h     = h,
            quote = quotes.get(sym, {}),
            gex   = gex_all.get(sym, {}),
            news  = news_all.get(sym, []),
        )
        path       = f"stocks/{sym}.md"
        commit_msg = f"Auto update {sym} GEX snapshot {date_str}"

        print(f"    📝 {path}...", end=" ", flush=True)
        ok = write_to_github(path, md, commit_msg)
        if ok:
            print("✅")
            success += 1
        time.sleep(1)  # GitHub API rate limit 禮貌間隔

    # 同時更新 stocks/README.md（索引）
    idx_md = f"# 持倉 GEX 快照索引\n\n最後更新：{date_str}\n\n"
    idx_md += "| 股票 | 名稱 | 連結 |\n|------|------|------|\n"
    for h in TOP10:
        idx_md += f"| {h['sym']} | {h['name']} | [查看]({h['sym']}.md) |\n"
    write_to_github("stocks/README.md", idx_md,
                    f"Auto update stocks index {date_str}")
    print(f"    📝 stocks/README.md ✅")

    print(f"\n{'═'*60}")
    print(f"  ✅ 完成！{success}/{len(TOP10)} 隻已上傳 GitHub")
    print(f"  🌐 https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/tree/main/stocks")
    print(f"{'═'*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
