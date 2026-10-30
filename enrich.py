# -*- coding: utf-8 -*-
"""
第3步 看营养：GO / KEGG 富集分析（直连 Enrichr 公开 API，不依赖 gseapy）

用法：
    python enrich.py --genes-file genes.csv --out enrich_results.csv
    python enrich.py --genes "TP53,EGFR,KRAS"

原理：
    1. 把基因列表 POST 到 Enrichr 的 addList 接口，拿到一个 userListId
    2. 用 userListId 逐个查询基因集库（GO BP / KEGG / Reactome / Hallmark）
    3. 本地做 BH 多重检验校正，输出显著条目

为什么不用 gseapy：
    gseapy 内部也是调这个接口，但它自带的 Rust 扩展在部分 Windows 机器上加载失败。
    直连 API 效果一样，还少一个依赖，答辩时也能直接报出接口地址。
"""

import argparse
import sys
import time

import pandas as pd
import requests

import config

ENRICHR = "https://maayanlab.cloud/Enrichr"

# 各方向查哪些库，由 config.P["enrichr_libs"] 决定（切换方向只改配置）
DEFAULT_LIBS = {
    "GO_Biological_Process_2023": "GO 生物学过程",
    "KEGG_2021_Human": "KEGG 通路",
    "Reactome_2022": "Reactome 通路",
    "MSigDB_Hallmark_2020": "Hallmark 基因集",
}


def bh_correct(pvals):
    """Benjamini-Hochberg 校正，返回与输入同序的 q 值。"""
    n = len(pvals)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [0.0] * n
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = n - rank          # 从最大的 p 往回走
        val = pvals[i] * n / (i + 1)
        prev = min(prev, val)
        q[i] = prev
    return q


def post_list(genes, retries=3):
    """把基因列表提交给 Enrichr，返回 userListId。"""
    payload = "\n".join(genes)
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(
                f"{ENRICHR}/addList",
                files={"file": (None, payload)},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            if "userListId" not in data:
                raise RuntimeError(f"返回异常: {str(data)[:200]}")
            return data["userListId"]
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"提交基因列表失败: {last}")


def query_lib(user_list_id, library, retries=3):
    """查询单个基因集库。"""
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(
                f"{ENRICHR}/enrich",
                params={"userListId": user_list_id, "backgroundType": library},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            return data.get(library, [])
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    print(f"  查询 {library} 失败: {last}", file=sys.stderr)
    return []


def run(genes, q_cutoff=0.05, top_n=10, libs=None):
    genes = [g for g in genes if g]
    if len(genes) < 2:
        raise ValueError("Enrichr 至少需要 2 个输入条目")

    # 库列表来自配置；某方向没配库时给出明确说明，而不是静默失败
    libs = libs or config.P.get("enrichr_libs") or {}
    if not libs:
        note = config.P.get("enrich_note") or "当前方向未配置富集库"
        raise RuntimeError(f"该方向暂不支持富集分析：{note}")

    print(f"提交 {len(genes)} 个{config.P['entity_label']}到 Enrichr ...", file=sys.stderr)
    uid = post_list(genes)
    print(f"  userListId = {uid}", file=sys.stderr)

    all_rows = []
    for lib, cn in libs.items():
        entries = query_lib(uid, lib)
        if not entries:
            print(f"  {cn}: 无结果", file=sys.stderr)
            continue

        pvals = [float(e[2]) for e in entries]
        qvals = bh_correct(pvals)

        for e, q in zip(entries, qvals):
            genes_hit = e[5] if len(e) > 5 and isinstance(e[5], list) else []
            all_rows.append({
                "基因集库": cn,
                "库ID": lib,
                "Term": e[1],
                "P值": float(e[2]),
                "校正P值(BH)": q,
                "重叠基因数": len(genes_hit),
                "重叠基因": "; ".join(genes_hit),
                "CombinedScore": float(e[4]) if len(e) > 4 else None,
                "排名": int(e[0]) if len(e) > 0 else None,
            })
        print(f"  {cn}: {len(entries)} 个条目", file=sys.stderr)

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    df = df.sort_values(["基因集库", "P值"])
    sig = df[df["校正P值(BH)"] <= q_cutoff].copy()
    return df, sig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genes")
    ap.add_argument("--genes-file")
    ap.add_argument("--profile", default=None,
                    help=f"切换研究方向：{', '.join(config.PROFILES)}")
    ap.add_argument("--out", default="enrich_results.csv")
    ap.add_argument("--q", type=float, default=0.05, help="BH 校正后阈值")
    ap.add_argument("--top", type=int, default=5, help="每个库打印前几条")
    args = ap.parse_args()

    if args.profile:
        config.set_profile(args.profile)

    if args.genes_file:
        with open(args.genes_file, "r", encoding="utf-8-sig") as f:
            genes = [ln.strip() for ln in f
                     if ln.strip() and ln.strip().lower() not in ("gene", "genes", "基因")]
    else:
        genes = [g.strip() for g in (args.genes or "").split(",") if g.strip()]

    if not genes:
        print("没有输入条目")
        sys.exit(1)

    print(f"当前方向：{config.describe()}", file=sys.stderr)
    try:
        df, sig = run(genes, q_cutoff=args.q)
    except RuntimeError as e:
        print(f"\n{e}")
        return

    if df.empty:
        print("\n没有拿到任何富集结果（可能是基因数太少，或接口临时不可用）")
        return

    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\n共 {len(df)} 条富集条目，其中显著（q<={args.q}）{len(sig)} 条")
    print(f"已保存：{args.out}\n")

    for lib_cn in df["基因集库"].unique():
        sub = sig[sig["基因集库"] == lib_cn].head(args.top)
        if sub.empty:
            continue
        print(f"【{lib_cn}】显著条目 Top{len(sub)}")
        for _, r in sub.iterrows():
            term = str(r["Term"]).split(" (GO:")[0]
            print(f"  q={r['校正P值(BH)']:.2e}  {term[:60]}  ({r['重叠基因数']} 个基因)")
        print()


if __name__ == "__main__":
    main()
