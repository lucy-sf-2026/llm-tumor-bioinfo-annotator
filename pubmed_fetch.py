"""
PubMed 文献抓取模块（基于 Bio.Entrez）

用法：
    python pubmed_fetch.py "EGFR AND lung adenocarcinoma" --max 20 --out result.csv

在 Streamlit 里调用：
    from pubmed_fetch import search_and_fetch, to_dataframe
    recs = search_and_fetch("TP53 AND lung cancer", retmax=50)

合规要点（NCBI 官方要求，答辩也会问）：
    1. 必须设置 Entrez.email，否则 NCBI 可能封 IP
    2. 无 API key 时限速 3 次/秒，有 key 可到 10 次/秒
    3. 大批量抓取请用 history 模式或分批，别循环打单条请求
"""

import os
import re
import sys
import time
import argparse
from dataclasses import dataclass, asdict, field

from Bio import Entrez

# ---- 身份标识：NCBI 要求必须提供，建议用环境变量传入 ----
Entrez.email = os.environ.get("NCBI_EMAIL", "your_email@example.com")
Entrez.tool = os.environ.get("NCBI_TOOL", "ChallengeCup-PubMedMiner")

API_KEY = os.environ.get("NCBI_API_KEY") or None
if API_KEY:
    Entrez.api_key = API_KEY

# 有 key 每请求 <0.11s，无 key <0.34s
MIN_INTERVAL = 0.11 if API_KEY else 0.34
_last_call = [0.0]

MAX_RETRY = 3
RETRY_SLEEP = 2.0


def _pace():
    """控制请求频率，避免触发 NCBI 限速。"""
    wait = MIN_INTERVAL - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _retry(func, *args, **kwargs):
    """带退避重试的调用包装。"""
    last = None
    for attempt in range(MAX_RETRY):
        try:
            _pace()
            return func(*args, **kwargs)
        except Exception as e:  # 网络抖动、限速、临时 5xx
            last = e
            if attempt < MAX_RETRY - 1:
                time.sleep(RETRY_SLEEP * (attempt + 1))
    raise RuntimeError(f"NCBI 请求失败（已重试 {MAX_RETRY} 次）: {last}") from last


@dataclass
class Article:
    pmid: str = ""
    title: str = ""
    abstract: str = ""
    journal: str = ""
    year: str = ""
    doi: str = ""
    authors: list = field(default_factory=list)
    pubtypes: list = field(default_factory=list)
    mesh: list = field(default_factory=list)


def _text(el):
    """取元素内全部文本（含 <i>、<sup> 等子标签），并清理多余空白。"""
    if el is None:
        return ""
    raw = "".join(el.itertext())
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def search(query, retmax=20, mindate=None, maxdate=None, sort="relevance"):
    """esearch：返回 PMID 列表。"""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "xml",   # Entrez.read 只能解析 XML，别改成 json
        "sort": sort,
    }
    if mindate:
        params["mindate"] = mindate
    if maxdate:
        params["maxdate"] = maxdate
    if mindate or maxdate:
        params["datetype"] = "pdat"

    def _do():
        return Entrez.esearch(**params)

    handle = _retry(_do)
    try:
        data = Entrez.read(handle)
    finally:
        handle.close()

    pmids = data.get("IdList", [])
    total = int(data.get("Count", 0))
    print(f"[esearch] 命中 {total} 条，本次取 {len(pmids)} 条", file=sys.stderr)
    return pmids, total


def fetch(pmids, batch_size=150):
    """efetch：按 PMID 批量取详情并解析。"""
    results = []
    pmids = [str(p) for p in pmids]
    for i in range(0, len(pmids), batch_size):
        chunk = pmids[i:i + batch_size]

        def _do():
            return Entrez.efetch(db="pubmed", id=",".join(chunk),
                                 retmode="xml", rettype="abstract")

        handle = _retry(_do)
        try:
            xml_bytes = handle.read()
        finally:
            handle.close()

        results.extend(_parse_xml(xml_bytes))
        print(f"[efetch] 已解析 {len(results)}/{len(pmids)}", file=sys.stderr)

    return results


def _parse_xml(xml_bytes):
    """解析 PubMedArticle XML（用标准库，比 Entrez.read 快且字段可控）。"""
    import xml.etree.ElementTree as ET

    articles = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"[parse] XML 解析失败: {e}", file=sys.stderr)
        return articles

    for node in root.findall(".//PubmedArticle"):
        a = Article()
        a.pmid = _text(node.find(".//MedlineCitation/PMID"))
        a.title = _text(node.find(".//ArticleTitle"))

        # 摘要可能分段（BACKGROUND/METHODS...），保留小标题
        parts = []
        for ab in node.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            body = _text(ab)
            if not body:
                continue
            parts.append(f"{label}: {body}" if label else body)
        a.abstract = " ".join(parts)

        a.journal = _text(node.find(".//Journal/Title"))

        year = _text(node.find(".//JournalIssue/PubDate/Year"))
        if not year:
            year = _text(node.find(".//JournalIssue/PubDate/MedlineDate"))
            year = re.search(r"\d{4}", year).group(0) if re.search(r"\d{4}", year) else year
        a.year = year

        for aid in node.findall(".//ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                a.doi = _text(aid)
                break

        for au in node.findall(".//AuthorList/Author"):
            last, ini = _text(au.find("LastName")), _text(au.find("Initials"))
            if last:
                a.authors.append(f"{last} {ini}".strip())

        a.pubtypes = [_text(pt) for pt in node.findall(".//PublicationTypeList/PublicationType")]
        a.mesh = [_text(m) for m in node.findall(".//MeshHeading/DescriptorName")]

        articles.append(a)

    return articles


def search_and_fetch(query, retmax=20, mindate=None, maxdate=None, sort="relevance"):
    """检索 + 抓取一步到位。"""
    pmids, _ = search(query, retmax=retmax, mindate=mindate,
                      maxdate=maxdate, sort=sort)
    if not pmids:
        return []
    return fetch(pmids)


def to_dataframe(articles):
    """转 pandas DataFrame，方便丢进 Streamlit 展示 / 导出 csv。"""
    import pandas as pd

    rows = []
    for a in articles:
        rows.append({
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
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description="PubMed 批量抓取（Bio.Entrez）")
    ap.add_argument("query", help="检索式，例如 'EGFR AND lung adenocarcinoma'")
    ap.add_argument("--max", type=int, default=20, help="最多取多少条，默认 20")
    ap.add_argument("--out", default="pubmed_result.csv", help="输出 csv 路径")
    ap.add_argument("--mindate", default=None, help="起始日期 YYYY/MM/DD")
    ap.add_argument("--maxdate", default=None, help="结束日期 YYYY/MM/DD")
    args = ap.parse_args()

    if Entrez.email == "your_email@example.com":
        print("提示：未设置 NCBI_EMAIL 环境变量，正在使用占位邮箱。"
              "正式使用请设置真实邮箱，否则可能被 NCBI 限流。\n", file=sys.stderr)

    articles = search_and_fetch(args.query, retmax=args.max,
                                mindate=args.mindate, maxdate=args.maxdate)
    if not articles:
        print("没有检索到结果")
        return

    df = to_dataframe(articles)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"\n共 {len(df)} 条，已保存到 {args.out}\n")

    for _, r in df.head(3).iterrows():
        print(f"PMID {r['PMID']} | {r['期刊']} {r['年份']} | DOI {r['DOI'] or '-'}")
        print(f"  {r['标题']}")
        print(f"  摘要: {(r['摘要'][:160] + '...') if len(r['摘要']) > 160 else r['摘要']}\n")


if __name__ == "__main__":
    main()
