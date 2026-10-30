# -*- coding: utf-8 -*-
"""
第5步 大厨总结：把抓到的摘要交给 LLM，强制只依据原文、强制标 PMID

用法：
    # 先看提示词长什么样（不花钱、不需要 key）
    python llm_summarize.py --in pubmed_batch.csv --dry-run

    # 真正调用
    set "LLM_API_KEY=sk-xxx"
    python llm_summarize.py --in pubmed_batch.csv --out llm_summaries.csv

支持任何 OpenAI 兼容接口（DeepSeek / 通义 / 智谱 / Kimi / 本地 Ollama）：
    set "LLM_BASE_URL=https://api.deepseek.com"
    set "LLM_MODEL=deepseek-chat"
"""

import argparse
import json
import os
import re
import sys
import time

import pandas as pd
import requests

import config

# ---------- 配置 ----------
API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

MAX_ABSTRACT_CHARS = 1200   # 每篇摘要截断长度，控制 token
MAX_ARTICLES = 6            # 每个基因最多喂几篇


def build_system_prompt():
    """提示词随方向变化：实体叫法、领域词都从 config 来。"""
    entity = config.P["entity_label"]
    domain = config.P["domain"]
    return f"""你是一名严谨的{domain}文献助手。

绝对规则（违反即视为错误答案）：
1. 只能使用【用户提供的文献摘要】中的信息，禁止引入任何外部知识或常识补充。
2. 每一条结论后面必须紧跟 PMID，格式为 [PMID:12345678]。无法标注 PMID 的结论一律不许输出。
3. 如果提供的摘要不足以支撑任何结论，只输出空数组 []，禁止编造。
4. 禁止使用"研究表明""众所周知"这类无出处的表述。
5. 不要复述摘要原文，要做归纳，但归纳的每一个事实都必须在摘要中有对应依据。
6. 结论围绕【{entity}】本身展开，不要跑题到无关对象。

输出格式：严格的 JSON 数组，不要任何解释文字、不要 markdown 代码块：
[
  {{"gene": "示例", "finding": "一句话结论", "pmid": "12345678"}}
]"""


# 兼容旧代码里直接引用 SYSTEM_PROMPT 的地方
SYSTEM_PROMPT = build_system_prompt()


def build_prompt(gene, rows):
    """把一个条目下的文献拼成提示词。"""
    entity = config.P["entity_label"]
    domain = config.P["domain"]
    blocks = []
    for i, r in enumerate(rows[:MAX_ARTICLES], 1):
        abstract = str(r["摘要"])[:MAX_ABSTRACT_CHARS]
        blocks.append(
            f"[文献{i}] PMID:{r['PMID']}\n"
            f"标题：{r['标题']}\n"
            f"期刊/年份：{r['期刊']} ({r['年份']})\n"
            f"摘要：{abstract}"
        )
    refs = "\n\n".join(blocks)
    return (
        f"{entity}：{gene}\n\n"
        f"以下是该{entity}相关的 PubMed 文献摘要：\n\n{refs}\n\n"
        f"请基于以上摘要，归纳 3-5 条关于 {gene} 在{domain}中的关键结论。"
        f"每条都要标注对应的 PMID。"
    )


def call_llm(prompt, temperature=0.0, retries=2):
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": 8000,   # 思考型模型先推理再作答，额度给小了会只剩推理没有 JSON
    }

    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=180)
            # 限流/网关抖动：退避后重试
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()

            data = r.json()
            msg = data["choices"][0].get("message", {}) or {}

            # 思考型模型会先输出推理过程，字段名各平台不统一：
            #   智谱/DeepSeek: reasoning_content
            #   GLM-5.2 等网关: reasoning
            # 推理会消耗 token，若 max_tokens 偏小则 content 直接为 null
            content = msg.get("content")
            if not content:
                content = msg.get("reasoning_content") or msg.get("reasoning")
            if not content:
                fr = data["choices"][0].get("finish_reason")
                raise RuntimeError(
                    f"模型返回空内容（finish_reason={fr}）。"
                    "多为 max_tokens 被推理过程吃光，请调大 max_tokens 或换非思考型模型"
                )
            return content

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(4 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            raise

    raise RuntimeError(f"请求失败（已重试 {retries} 次）: {last_err}")


STRICT_SUFFIX = (
    "\n\n【输出要求】不要输出任何分析过程、思考步骤或解释。"
    "第一个字符必须是 [，最后一个字符必须是 ]。"
)


def summarize_gene(gene, rows):
    """一个条目的完整流程：调用 → 解析 → 失败追一次 → 仍失败返回空。

    CLI 和网页端都调这个函数，避免两套逻辑不一致。
    返回 (items, raw_text)。
    """
    prompt = build_prompt(gene, rows)
    raw = call_llm(prompt)
    items = parse_json_array(raw)

    if not items:
        # 常见原因：模型把思考过程写进了正文，JSON 没生成出来。追一次严格指令。
        raw = call_llm(prompt + STRICT_SUFFIX)
        items = parse_json_array(raw)

    return items, raw


def parse_json_array(text):
    """从模型输出里抠出 JSON 数组，容忍它加代码块或解释。"""
    if not text:
        return []
    text = str(text).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return []


def clean_finding(text):
    """去掉结论里的 [PMID:xxx] 标记（PMID 已单独成列，正文里重复没必要）。"""
    text = str(text).strip()
    # 任意位置的 PMID 标记都清掉，容忍 "[PMID:3945" 这种被截断的半截
    text = re.sub(r"[\s]*[\[\(]?\s*(?:PMI[D]?|PMID)[:\s]*\d+\s*[\]\)]?", "",
                  text, flags=re.I)
    # 清理残留的孤立括号和多余空格
    text = re.sub(r"[\s]*[\[\(]\s*[\]\)]", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="pubmed_batch.csv")
    ap.add_argument("--out", default="llm_summaries.csv")
    ap.add_argument("--dry-run", action="store_true", help="只打印提示词，不调用 API")
    ap.add_argument("--gene", help="只处理某一个条目")
    ap.add_argument("--profile", default=None,
                    help=f"切换研究方向：{', '.join(config.PROFILES)}")
    args = ap.parse_args()

    if args.profile:
        config.set_profile(args.profile)

    df = pd.read_csv(args.infile)
    df = df[df["摘要"].fillna("").astype(str).str.len() > 50]   # 丢掉无摘要的

    if df.empty:
        print("没有可用摘要，先检查输入文件")
        sys.exit(1)

    groups = df.groupby("基因", sort=False)
    if args.gene:
        groups = [(args.gene, df[df["基因"] == args.gene])]

    if args.dry_run:
        gene, rows = list(groups)[0]
        print("=" * 70)
        print("SYSTEM PROMPT")
        print("=" * 70)
        print(build_system_prompt())
        print("\n" + "=" * 70)
        print(f"USER PROMPT（示例基因：{gene}）")
        print("=" * 70)
        print(build_prompt(gene, rows.to_dict("records")))
        print("\n" + "=" * 70)
        print(f"[dry-run] 未调用 API。共 {len(list(groups))} 个基因待总结。")
        return

    if not API_KEY:
        print("缺少 LLM_API_KEY 环境变量。先设：\n"
              '  set "LLM_API_KEY=你的key"\n'
              "或者用 --dry-run 先看提示词")
        sys.exit(1)

    results = []
    for i, (gene, rows) in enumerate(groups, 1):
        print(f"[{i}/{len(list(groups))}] 总结 {gene} ...", file=sys.stderr)
        try:
            items, raw = summarize_gene(gene, rows.to_dict("records"))
        except Exception as e:
            print(f"    {gene} 调用失败: {type(e).__name__}: {e}", file=sys.stderr)
            continue

        valid_pmids = set(str(p) for p in rows["PMID"])

        if not items:
            snippet = " ".join(str(raw).split())[:200]
            print(f"    {gene} 未返回有效结论。原始返回前 200 字：{snippet}",
                  file=sys.stderr)

        for it in items:
            if not isinstance(it, dict):
                continue
            pmid = str(it.get("pmid", "")).strip()
            finding = clean_finding(it.get("finding", ""))
            if not finding:
                continue
            # 幻觉拦截：PMID 必须真实存在于本次抓取的文献里
            ok = pmid in valid_pmids
            results.append({
                "基因": gene,
                "结论": finding,
                "PMID": pmid,
                "溯源校验": "通过" if ok else "PMID 不在本次文献中，已标红",
            })
        time.sleep(1.5)   # 网关对连续请求敏感，间隔拉长可明显降低失败率

    if not results:
        print("没有产出任何结论")
        return

    out = pd.DataFrame(results)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    total = len(out)
    bad = int((out["溯源校验"] != "通过").sum())
    print(f"\n完成：{total} 条结论，已保存 {args.out}")
    print(f"溯源校验：通过 {total - bad} 条，可疑 {bad} 条")
    if bad:
        print("可疑条目说明模型引用了不存在的 PMID，这正是要拦截的幻觉")

    # 各基因产出，方便发现"静默返回空"的基因
    counts = out["基因"].value_counts()
    print("\n各基因产出条数：")
    for gene in [g for g, _ in groups]:
        n = int(counts.get(gene, 0))
        flag = "   ← 没产出，建议单独重跑 --gene " + gene if n == 0 else ""
        print(f"  {gene:<10} {n} 条{flag}")


if __name__ == "__main__":
    main()
