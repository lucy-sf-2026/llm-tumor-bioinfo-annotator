# -*- coding: utf-8 -*-
"""
第6步 拼装炒菜机：Streamlit 网页界面

运行：
    streamlit run app.py

然后浏览器会自动打开 http://localhost:8501
"""

import io
import os
import time

import pandas as pd
import streamlit as st

import batch_pubmed
import config
import enrich
import gene_convert
from pubmed_fetch import search, fetch
from llm_summarize import summarize_gene, clean_finding

st.set_page_config(page_title="生物实体注释与文献挖掘工具", page_icon="🧬", layout="wide")

st.title("🧬 生物实体注释与文献挖掘工具")
st.caption("ID标准化 → 功能富集 → PubMed文献抓取 → LLM约束总结（每条结论强制绑定PMID）")

# ---------------- 侧边栏 ----------------
with st.sidebar:
    st.header("研究方向")
    _keys = list(config.PROFILES.keys())
    _labels = [f"{config.PROFILES[k]['name']}" for k in _keys]
    _cur = _keys.index(config.current_key()) if config.current_key() in _keys else 0
    choice = st.selectbox("选择方向（切换后下面全部跟着变）", _labels, index=_cur)
    config.set_profile(_keys[_labels.index(choice)])
    st.caption(config.describe())
    if config.P.get("enrich_note"):
        st.warning(config.P["enrich_note"])

    st.divider()
    st.header("参数设置")
    disease = st.text_input("限定词（疾病/物种/主题）",
                            value=config.P.get("pubmed_default_disease", ""),
                            help="留空则不限定；例如 lung adenocarcinoma")
    per_gene = st.slider(f"每个{config.P['entity_label']}抓几篇文献", 1, 10, 5)
    q_cutoff = st.slider("富集显著性阈值 (BH校正)", 0.001, 0.2, 0.05, 0.01)

    st.divider()
    st.header("LLM 配置")
    api_key = st.text_input("API Key", type="password",
                            value=os.environ.get("LLM_API_KEY", ""))
    base_url = st.text_input("接口地址", value=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"))
    model = st.text_input("模型名", value=os.environ.get("LLM_MODEL", "deepseek-chat"))

# ---------------- 输入 ----------------
st.subheader(f"① 输入{config.P['entity_label']}列表")
default_genes = config.P["example_genes"]
txt = st.text_area(f"一行一个{config.P['entity_label']}（也可上传 csv，第一列是名称）",
                   default_genes, height=180)

uploaded = st.file_uploader("或上传 csv", type=["csv", "txt"])
if uploaded is not None:
    raw = uploaded.read().decode("utf-8-sig")
    lines = [x.split(",")[0].strip() for x in raw.splitlines() if x.strip()]
    txt = "\n".join([x for x in lines if x.lower() not in ("gene", "genes", "基因")])

genes = [g.strip().upper() for g in txt.replace(",", "\n").splitlines() if g.strip()]
st.write(f"当前{config.P['entity_label']}数：**{len(genes)}** —— {', '.join(genes)}")

if "results" not in st.session_state:
    st.session_state.results = {}

# ---------------- 步骤按钮 ----------------
c1, c2, c3, c4 = st.columns(4)
run_id = c1.button("② ID标准化", use_container_width=True)
run_enrich = c2.button("③ 富集分析", use_container_width=True)
run_pubmed = c3.button("④ 抓取文献", use_container_width=True)
run_llm = c4.button("⑤ LLM总结", use_container_width=True)

# ② ID 转换
if run_id:
    with st.spinner("查询 mygene ..."):
        try:
            st.session_state.results["ids"] = gene_convert.convert(genes)
        except Exception as e:
            st.error(f"ID 标准化失败：{e}")

if "ids" in st.session_state.results:
    st.subheader("ID 标准化结果")
    st.dataframe(st.session_state.results["ids"], use_container_width=True)

# ③ 富集
if run_enrich:
    with st.spinner("调用 Enrichr 富集接口 ..."):
        try:
            df_e, sig = enrich.run(genes, q_cutoff=q_cutoff)
            st.session_state.results["enrich"] = sig
        except Exception as e:
            st.error(f"富集失败：{e}")

if "enrich" in st.session_state.results:
    sig = st.session_state.results["enrich"]
    st.subheader(f"富集分析结果（显著条目 {len(sig)} 条）")
    libs = sig["基因集库"].unique().tolist()
    tabs = st.tabs(libs)
    for tab, lib in zip(tabs, libs):
        with tab:
            sub = sig[sig["基因集库"] == lib][["Term", "校正P值(BH)", "重叠基因数", "重叠基因"]]
            st.dataframe(sub.head(20), use_container_width=True)

# ④ 抓文献
if run_pubmed:
    rows, prog = [], st.progress(0.0)
    for i, g in enumerate(genes, 1):
        term = batch_pubmed.build_term(g, disease)
        try:
            pmids, _ = search(term, retmax=per_gene)
        except Exception:
            pmids = []
        if pmids:
            for a in fetch(pmids):
                rows.append({"基因": g, "PMID": a.pmid, "标题": a.title,
                             "摘要": a.abstract, "期刊": a.journal,
                             "年份": a.year, "DOI": a.doi})
        prog.progress(i / len(genes))
    st.session_state.results["papers"] = pd.DataFrame(rows).drop_duplicates(subset=["基因", "PMID"])

if "papers" in st.session_state.results:
    dfp = st.session_state.results["papers"]
    st.subheader(f"文献抓取结果（{len(dfp)} 条，{dfp['PMID'].nunique()} 篇不重复）")
    st.dataframe(dfp[["基因", "PMID", "年份", "期刊", "标题"]], use_container_width=True)
    st.download_button("下载文献表 csv",
                       dfp.to_csv(index=False).encode("utf-8-sig"),
                       "pubmed_batch.csv", "text/csv")

# ⑤ LLM
if run_llm:
    dfp = st.session_state.results.get("papers")
    if dfp is None or dfp.empty:
        st.warning("先执行第 ④ 步抓文献")
    elif not api_key:
        st.warning("先在侧边栏填 API Key")
    else:
        os.environ["LLM_API_KEY"] = api_key
        import llm_summarize
        llm_summarize.API_KEY = api_key
        llm_summarize.BASE_URL = base_url.rstrip("/")
        llm_summarize.MODEL = model

        out, bar = [], st.progress(0.0)
        dfp = dfp[dfp["摘要"].fillna("").astype(str).str.len() > 50]
        groups = list(dfp.groupby("基因", sort=False))
        for i, (g, rows_g) in enumerate(groups, 1):
            try:
                items, raw = summarize_gene(g, rows_g.to_dict("records"))
                valid = set(str(p) for p in rows_g["PMID"])
                if not items:
                    st.warning(f"{g} 未返回有效结论（已自动重试），"
                               f"原始返回前 80 字：{' '.join(str(raw).split())[:80]}")
                for it in items:
                    if isinstance(it, dict) and it.get("finding"):
                        pmid = str(it.get("pmid", "")).strip()
                        out.append({"基因": g, "结论": clean_finding(it["finding"]),
                                    "PMID": pmid,
                                    "溯源校验": "通过" if pmid in valid else "PMID不存在"})
            except Exception as e:
                st.error(f"{g} 调用失败：{e}")
                break
            bar.progress(i / len(groups))
            time.sleep(1.5)
        # 注：不要调用 bar.empty()，部分 Streamlit 版本会触发前端 removeChild 报错
        st.session_state.results["llm"] = pd.DataFrame(out)

if "llm" in st.session_state.results:
    dfl = st.session_state.results["llm"]
    st.subheader(f"LLM 约束总结（{len(dfl)} 条结论）")
    bad = int((dfl["溯源校验"] != "通过").sum())
    if bad:
        st.warning(f"有 {bad} 条结论引用了不存在的 PMID，已标记为幻觉")
    else:
        st.success("全部结论的 PMID 都能对应到本次抓取的文献")
    st.dataframe(dfl, use_container_width=True)
    st.download_button("下载总结 csv",
                       dfl.to_csv(index=False).encode("utf-8-sig"),
                       "llm_summaries.csv", "text/csv")
