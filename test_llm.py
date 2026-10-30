# -*- coding: utf-8 -*-
"""LLM 连接自检：验证 key / 地址 / 模型名是否正确，10 秒出结果。

用法：
    $env:LLM_API_KEY="你的key"
    $env:LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
    $env:LLM_MODEL="glm-5.2"
    python test_llm.py
"""

import json
import os
import sys

import requests

API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "glm-4-flash")

print(f"接口地址: {BASE_URL}")
print(f"模型名称: {MODEL}")
print(f"密钥:     {'已设置 (' + API_KEY[:6] + '...)' if API_KEY else '❌ 未设置'}\n")

if not API_KEY:
    print('先设置密钥：$env:LLM_API_KEY="你的key"')
    sys.exit(1)

url = f"{BASE_URL}/chat/completions"
payload = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": "只回复四个字：连接成功"}
    ],
    "temperature": 0,
    "max_tokens": 300,   # 思考型模型要先推理，给少了 content 会是 null
}

try:
    r = requests.post(url, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }, json=payload, timeout=60)
except Exception as e:
    print(f"❌ 网络层失败: {type(e).__name__}: {e}")
    print("   检查接口地址是否正确、是否需要代理")
    sys.exit(1)

print(f"HTTP 状态码: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
    content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning")
    usage = data.get("usage", {})
    if content:
        print(f"✅ 模型回复: {str(content).strip()[:100]}")
    else:
        print("⚠️ 连接成功，但正文为空（finish_reason=%s）—— 思考型模型把 token 用在推理上了"
              % (data.get("choices") or [{}])[0].get("finish_reason"))
    print(f"   实际调用模型: {data.get('model', MODEL)}")
    print(f"   本次消耗: 输入 {usage.get('prompt_tokens', '?')} tokens / "
          f"输出 {usage.get('completion_tokens', '?')} tokens")
    print("\n可以跑正式任务了。")
else:
    print("❌ 调用失败，返回内容：")
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:600])
    except Exception:
        print(r.text[:600])
    print("\n常见原因：")
    print("  · 模型名不对 -> 去智谱控制台复制准确的模型编码")
    print("  · key 失效或余额不足")
    print("  · 接口地址少了 /v4 或多了斜杠")
