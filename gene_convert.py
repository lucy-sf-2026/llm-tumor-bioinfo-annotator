# -*- coding: utf-8 -*-
"""
第2步 查户口：基因符号 -> Entrez ID

用法：
    python gene_convert.py --genes "TP53,EGFR,MYC"
    python gene_convert.py --genes-file genes.csv --out gene_ids.csv
"""

import argparse
import sys

import logging

import mygene
import pandas as pd

import config

logging.getLogger("biothings").setLevel(logging.WARNING)


def _pick_id(r, id_key):
    """从一行结果里取出目标 ID。

    mygene 会把 uniprot 拆成 uniprot.Swiss-Prot / uniprot.TrEMBL 两列，
    这里优先取 Swiss-Prot（人工审核），没有再退回 TrEMBL。
    """
    if id_key == "uniprot":
        for cand in ("uniprot.Swiss-Prot", "uniprot.TrEMBL"):
            val = r.get(cand)
            if isinstance(val, (list, tuple)):
                val = val[0] if val else None
            if val is not None and pd.notna(val):
                return val
        return None

    val = r.get(id_key)
    if isinstance(val, (list, tuple)):
        val = val[0] if val else None
    return val


def convert(genes, species=None, scopes=None, fields=None, id_column=None):
    """ID 标准化。参数默认取自 config，切换方向时无需改这里。"""
    species = species or config.P["species"]
    scopes = scopes or config.P["id_scopes"]
    fields = fields or config.P["id_fields"]
    id_column = id_column or config.P["id_column"]

    # UniProt 场景下真正的 ID 字段叫 uniprot
    id_key = "uniprot" if "uniprot" in fields.lower() else "entrezgene"

    mg = mygene.MyGeneInfo()

    res = mg.querymany(
        genes,
        scopes=scopes,
        fields=fields,
        species=species,
        as_dataframe=True,
        verbose=False,
    )

    rows = []
    for idx in res.index:
        query = idx[0] if isinstance(idx, tuple) else idx
        r = res.loc[idx]
        if isinstance(r, pd.DataFrame):      # 一个符号命中多条
            r = r.iloc[0]

        raw_id = _pick_id(r, id_key)

        found = raw_id is not None and pd.notna(raw_id)
        if found and id_key == "entrezgene":
            try:
                value = str(int(raw_id))
            except (TypeError, ValueError):
                value = str(raw_id)
        else:
            value = str(raw_id) if found else ""

        rows.append({
            "输入的符号": query,
            id_column: value,
            "官方全名": r.get("name") if pd.notna(r.get("name")) else "",
            "是否找到": "是" if found else "否",
        })
    return pd.DataFrame(rows).drop_duplicates(subset=["输入的符号"])


def read_genes(args):
    if args.genes_file:
        with open(args.genes_file, "r", encoding="utf-8-sig") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        return [x for x in lines if x.lower() not in ("gene", "genes", "基因")]
    return [g.strip() for g in (args.genes or "").split(",") if g.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genes")
    ap.add_argument("--genes-file")
    ap.add_argument("--species", default=None,
                    help="覆盖配置里的物种：human / mouse / arabidopsis 等")
    ap.add_argument("--profile", default=None,
                    help=f"切换研究方向：{', '.join(config.PROFILES)}")
    ap.add_argument("--out", default="gene_ids.csv")
    args = ap.parse_args()

    if args.profile:
        config.set_profile(args.profile)

    genes = read_genes(args)
    if not genes:
        print("没有基因")
        sys.exit(1)

    species = args.species or config.P["species"]
    print(f"查询 {len(genes)} 个{config.P['entity_label']}"
          f"（方向：{config.P['name']}｜物种：{species}）...\n", file=sys.stderr)
    df = convert(genes, species=args.species)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")

    print(df.to_string(index=False, max_colwidth=40))
    print(f"\n已保存：{args.out}")

    missing = df[df["是否找到"] == "否"]["输入的符号"].tolist()
    if missing:
        print(f"\n未找到：{', '.join(missing)}（检查拼写，或确认物种是否选对）")


if __name__ == "__main__":
    main()
