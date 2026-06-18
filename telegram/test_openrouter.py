"""
test_openrouter.py
═══════════════════════════════════════════════════
獨立測試 OpenRouter API 連接，唔需要跑完整Bot。

用途：快速確認 403 錯誤嘅根本原因
  - Key無效/未充值？
  - Model名稱錯誤？
  - 內容被guardrail攔截？
  - 純粹網絡問題？

執行：
  python test_openrouter.py
═══════════════════════════════════════════════════
"""

import requests
import json

# ⚠️ 填你嗰串OpenRouter key（同telegram_bot.py用同一個）
OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY"

# 主要測試model（如被拒絕，可改用其他model確認問題範圍）
# 例如："openai/gpt-4o-mini" 或 "google/gemini-2.0-flash-001"
PRIMARY_MODEL = "deepseek/deepseek-chat"     # 主要分析model（不受地區限制）
FALLBACK_MODEL = "qwen/qwen-2.5-72b-instruct"   # 對照測試用，確認非單一provider問題

def call_model(model_name: str, label: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/netng888-code/netng888",
        "X-Title": "GEX Monitor Bot Test",
    }
    payload = {
        "model": model_name,
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "請回覆「測試成功」兩個字"}],
    }

    print(f"\n{'─'*50}")
    print(f"  測試 {label}：{model_name}")
    print(f"{'─'*50}")

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"📥 HTTP狀態碼：{r.status_code}")
        body = r.json()
        print(f"📄 回應：\n{json.dumps(body, indent=2, ensure_ascii=False)[:600]}")

        if r.status_code == 200:
            content = body["choices"][0]["message"]["content"]
            print(f"\n✅ {label} 成功！回覆：{content}")
            return True
        else:
            print(f"\n❌ {label} 失敗 [{r.status_code}]")
            return False
    except Exception as e:
        print(f"\n❌ {label} 連接錯誤：{type(e).__name__}: {e}")
        return False

def test_connection():
    print("═" * 50)
    print("  OpenRouter API 連接測試")
    print("═" * 50)
    print(f"\n🔑 Key前綴：{OPENROUTER_API_KEY[:12]}..." if len(OPENROUTER_API_KEY) > 12 else "⚠️ Key似乎太短或未填")

    primary_ok = call_model(PRIMARY_MODEL, "DeepSeek（主要分析model）")

    if not primary_ok:
        print(f"\n\n{'═'*50}")
        print("  DeepSeek失敗，測試對照model")
        print(f"{'═'*50}")
        fallback_ok = call_model(FALLBACK_MODEL, "Qwen（對照組）")

        print(f"\n\n{'═'*50}")
        print("  診斷結論")
        print(f"{'═'*50}")
        if fallback_ok:
            print("✅ OpenRouter帳戶/Key本身正常（Qwen成功）")
            print("❌ 問題特定喺DeepSeek provider層（罕見）")
        else:
            print("❌ 連Qwen都失敗，問題在OpenRouter帳戶本身")
            print("   （Key無效、餘額問題、或帳戶被限制）")
    else:
        print(f"\n\n{'═'*50}")
        print("  ✅ 全部正常！DeepSeek可正常使用")
        print(f"{'═'*50}")

if __name__ == "__main__":
    test_connection()
