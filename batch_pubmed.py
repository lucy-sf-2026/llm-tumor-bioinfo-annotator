# -*- coding: utf-8 -*-
"""
批量版：读基因列表 -> 逐个检索 PubMed -> 去重抓摘要 -> 输出长表

用法：
    python batch_pubmed.py --genes "EGFR,TP53,KRAS,ALK" --disease "lung adenocarcinoma" --per-gene 5
    python batch_pubmed.py --genes-file genes.csv --disease "lung cancer" --per-gene 10

输出：pubmed_batch.csv
    每行 = 一个基因 × 一条文献，保留 基因 列，方便回溯"这条证据支持哪个基因"
"""

import argparse
import csv
import sys
import time

import pandas as pd

import config
from pubmed_fetch import search, fetch


def build_term(name, disease):
    """按配置里的模板拼检索式，换方向只改 config。"""
    disease_part = f" AND ({disease})" if disease else ""
    template = config.P.get("pubmed_template") or "({name}){disease_part}"
    return template.format(name=name, disease=disease or "", disease_part=disease_part)


def read_genes(args):
    """支持命令行直接给，或从 csv/txt 读。"""
    if args.genes_file:
        path = args.genes_file
        genes = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if not row:
                    continue
                val = row[0].strip()
                if not val:
                    continue
                # 跳过表头
                if i == 0 and val.lower() in ("gene", "genes", "基因", "symbol"):
                    continue
                genes.append(val)
    else:
        genes = [g.strip() for g in (args.genes or "").split(",") if g.strip()]

    # 去重保序
    seen, out = set(), []
    for g in genes:
        k = g.upper()
        if k not in seen:
            seen.add(k)
            out.append(g)
    return out


def main():
    ap = argparse.ArgumentParser(description="批量抓取 PubMed 文献")
    ap.add_argument("--genes", help="逗号分隔的基因列表")
    ap.add_argument("--genes-file", help="基因列表文件（csv/txt，每行一个）")
    ap.add_argument("--disease", default=None,
                    help="疾病/限定词；不填则用配置里的默认值")
    ap.add_argument("--per-gene", type=int, default=5, help="每个基因最多取几条，默认 5")
    ap.add_argument("--mindate", default=None, help="起始日期，格式 2020/01/01")
    ap.add_argument("--maxdate", default=None, help="结束日期，格式 2025/12/31")
    ap.add_argument("--profile", default=None,
                    help=f"切换研究方向：{', '.join(config.PROFILES)}")
    ap.add_argument("--out", default="pubmed_batch.csv", help="输出 csv 路径")
    args = ap.parse_args()

    if args.profile:
        config.set_profile(args.profile)

    # 没显式给 --disease 时，用当前方向的默认限定词
    disease = args.disease if args.disease is not None else config.P.get("pubmed_default_disease", "")

    genes = read_genes(args)
    if not genes:
        print("没有读到基因列表，请用 --genes 或 --genes-file 指定")
        sys.exit(1)

    print(f"当前方向：{config.describe()}", file=sys.stderr)
    print(f"共 {len(genes)} 个{config.P['entity_label']}，每个最多 {args.per_gene} 条"
          f"（疾病限定词：{disease or '不限'}）\n", file=sys.stderr)

    gene2pmids = {}
    all_pmids = []

    for idx, gene in enumerate(genes, 1):
        term = build_term(gene, disease)
        try:
            pmids, total = search(term, retmax=args.per_gene,
                                  mindate=args.mindate, maxdate=args.maxdate)
        except Exception as e:
            print(f"  [{idx}/{len(genes)}] {gene} 检索失败: {e}", file=sys.stderr)
            gene2pmids[gene] = []
            continue

        gene2pmids[gene] = pmids
        all_pmids.extend(pmids)
        print(f"  [{idx}/{len(genes)}] {gene}: 命中 {total}，取 {len(pmids)}",
              file=sys.stderr)

    # 去重后一次 efetch，避免重复请求
    unique_pmids = list(dict.fromkeys(all_pmids))
    print(f"\n合计 {len(all_pmids)} 条引用，去重后 {len(unique_pmids)} 篇，开始抓摘要",
          file=sys.stderr)

    if not unique_pmids:
        print("没有命中任何文献")
        return

    articles = fetch(unique_pmids)
    by_pmid = {a.pmid: a for a in articles}

    # 组装长表：基因 × 文献
    rows = []
    for gene in genes:
        for pmid in gene2pmids.get(gene, []):
            a = by_pmid.get(str(pmid))
            if not a:
                continue
            rows.append({
                "基因": gene,
                "PMID": a.pmid,
                "标题": a.title,
                "摘要": a.abstract,
                "期刊": a.journal,
                "年份": a.year,
                "DOI": a.doi,
                "作者": ", ".join(a.authors[:5]) + (" 等" if len(a.authors) > 5 else ""),
                "文献类型": "; ".join(a.pubtypes),
                "MeSH": "; ".join(a.mesh[:8]),
            })

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")

    print(f"\n完成：{len(df)} 行（基因×文献），{df['PMID'].nunique()} 篇不重复文献")
    print(f"已保存：{args.out}")

    print("\n各基因命中情况：")
    for gene in genes:
        n = len(gene2pmids.get(gene, []))
        flag = "  ← 没抓到，建议放宽检索式或该基因确实无文献" if n == 0 else ""
        print(f"  {gene:<12} {n} 条{flag}")

    if len(df):
        empty = int((df["摘要"].fillna("") == "").sum())
        if empty:
            print(f"\n注意：{empty} 行没有摘要（PubMed 本身缺失），喂给大模型前要过滤掉")


if __name__ == "__main__":
    main()
