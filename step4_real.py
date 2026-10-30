# -*- coding: utf-8 -*-
"""
阶段 4：接真实接口（完整版）

运行：
    streamlit run step4_real.py

和阶段 3 的区别：假数据换成真函数调用。
业务逻辑一行没改 —— 因为它们在独立模块里（gene_convert.py / enrich.py / ...）。

这一阶段学三件事：
    1. try/except 把报错显示在页面上，而不是让页面崩掉
    2. st.progress 让用户知道跑到哪了
    3. 把配置（key/地址/模型）放到侧边栏，不写死在代码里
"""

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

st.set_page_config(page_title="生物实体注释工具", page_icon="🧬", layout="wide")
st.title("🧬 生物实体注释与文献挖掘工具")
st.caption("ID标准化 → 功能富集 → 文献抓取 → LLM 约束总结")

# ============ 侧边栏 ============
with st.sidebar:
    st.header("研究方向")
    _keys = list(config.PROFILES.keys())
    _labels = [config.PROFILES[k]["name"] for k in _keys]
    _cur = _keys.index(config.current_key()) if config.current_key() in _keys else 0
    _choice = st.selectbox("选择方向", _labels, index=_cur)
    config.set_profile(_keys[_labels.index(_choice)])
    st.caption(config.describe())
    if config.P.get("enrich_note"):
        st.warning(config.P["enrich_note"])

    st.divider()
    st.header("参数设置")
    disease = st.text_input("限定词（疾病/物种/主题）",
                            value=config.P.get("pubmed_default_disease", ""))
    per_gene = st.slider(f"每个{config.P['entity_label']}抓几篇", 1, 10, 5)
    q_cutoff = st.slider("富集显著性阈值", 0.001, 0.2, 0.05, 0.01)

    st.divider()
    st.header("LLM 配置")
    api_key = st.text_input("API Key", type="password",
                            value=os.environ.get("LLM_API_KEY", ""))
    base_url = st.text_input("接口地址",
                             value=os.environ.get("LLM_BASE_URL", "https://api.aixapex.com/v1"))
    model = st.text_input("模型名", value=os.environ.get("LLM_MODEL", "TPK/GLM-5.2"))

# ============ 输入 ============
st.subheader(f"① {config.P['entity_label']}列表")
default_genes = config.P["example_genes"]
_txt = st.text_area(f"一行一个{config.P['entity_label']}", default_genes, height=160)
genes = [g.strip().upper()
         for g in _txt.replace(",", "\n").splitlines() if g.strip()]
st.write(f"识别到 **{len(genes)}** 个{config.P['entity_label']}")

if "res" not in st.session_state:
    st.session_state.res = {}

# ============ 四个按钮 ============
st.subheader("② 执行")
c1, c2, c3, c4 = st.columns(4)
b_id = c1.button("ID 转换", use_container_width=True)
b_en = c2.button("富集分析", use_container_width=True)
b_pm = c3.button("抓取文献", use_container_width=True)
b_llm = c4.button("LLM 总结", use_container_width=True)

# ---- ID 转换 ----
if b_id:
    try:
        with st.spinner("查询 mygene ..."):
            st.session_state.res["ids"] = gene_convert.convert(genes)
        st.success("ID 转换完成")
    except Exception as e:
        st.error(f"失败：{type(e).__name__}: {e}")

# ---- 富集 ----
if b_en:
    try:
        with st.spinner("调用 Enrichr（大约 5~10 秒）..."):
            full, sig = enrich.run(genes, q_cutoff=q_cutoff)
        st.session_state.res["enrich"] = sig
        st.success(f"完成：{len(full)} 条，显著 {len(sig)} 条")
    except Exception as e:
        st.error(f"失败：{type(e).__name__}: {e}")

# ---- 抓文献 ----
if b_pm:
    rows = []
    bar = st.progress(0.0, text="准备中...")
    for i, g in enumerate(genes, 1):
        term = batch_pubmed.build_term(g, disease)
        try:
            pmids, _ = search(term, retmax=per_gene)
            for a in fetch(pmids):
                rows.append({"基因": g, "PMID": a.pmid, "标题": a.title,
                             "摘要": a.abstract, "期刊": a.journal,
                             "年份": a.year, "DOI": a.doi})
        except Exception as e:
            st.warning(f"{g} 抓取失败：{e}")
        bar.progress(i / len(genes), text=f"已完成 {g}（{i}/{len(genes)}）")
    # 注：不调用 bar.empty()，部分 Streamlit 版本会触发前端 removeChild 报错
    st.session_state.res["papers"] = pd.DataFrame(rows).drop_duplicates(
        subset=["基因", "PMID"])
    st.success(f"抓到 {len(rows)} 条")

# ---- LLM ----
if b_llm:
    dfp = st.session_state.res.get("papers")
    if dfp is None or dfp.empty:
        st.warning("先点「抓取文献」")
    elif not api_key:
        st.warning("侧边栏填 API Key")
    else:
        import llm_summarize
        llm_summarize.API_KEY = api_key
        llm_summarize.BASE_URL = base_url.rstrip("/")
        llm_summarize.MODEL = model

        dfp = dfp[dfp["摘要"].fillna("").astype(str).str.len() > 50]
        out = []
        groups = list(dfp.groupby("基因", sort=False))
        bar = st.progress(0.0, text="总结中...")
        for i, (g, sub) in enumerate(groups, 1):
            try:
                items, raw = summarize_gene(g, sub.to_dict("records"))
                valid = set(str(x) for x in sub["PMID"])
                if not items:
                    st.warning(f"{g} 未返回有效结论（已自动重试一次仍失败），"
                               f"原始返回前 80 字：{' '.join(str(raw).split())[:80]}")
                for it in items:
                    if isinstance(it, dict) and it.get("finding"):
                        pmid = str(it.get("pmid", "")).strip()
                        out.append({"基因": g,
                                    "结论": clean_finding(it["finding"]),
                                    "PMID": pmid,
                                    "溯源校验": "通过" if pmid in valid else "PMID不存在"})
            except Exception as e:
                st.warning(f"{g} 失败：{e}")
            bar.progress(i / len(groups), text=f"已总结 {g}")
            time.sleep(1.5)   # 避免连续请求被网关限流
        # 注：不调用 bar.empty()，部分 Streamlit 版本会触发前端 removeChild 报错
        ok_genes = len(set(r["基因"] for r in out)) if out else 0
        st.session_state.res["llm"] = pd.DataFrame(out)
        if out and ok_genes < len(groups):
            st.warning(f"只有 {ok_genes}/{len(groups)} 个{config.P['entity_label']}成功，"
                       f"其余失败请查看上面的黄色提示，或用命令行重跑")

# ============ 展示 ============
st.subheader("③ 结果")
res = st.session_state.res

if "ids" in res:
    st.markdown("**ID 转换**")
    st.dataframe(res["ids"], use_container_width=True)

if "enrich" in res:
    df = res["enrich"]
    st.markdown(f"**富集结果：{len(df)} 条显著**")
    tabs = st.tabs(df["基因集库"].unique().tolist())
    for tab, lib in zip(tabs, df["基因集库"].unique()):
        with tab:
            sub = df[df["基因集库"] == lib][["Term", "校正P值(BH)", "重叠基因数", "重叠基因"]]
            st.dataframe(sub.head(20), use_container_width=True)
    st.download_button("下载富集结果", df.to_csv(index=False).encode("utf-8-sig"),
                       "enrich_results.csv", "text/csv")

if "papers" in res:
    dfp = res["papers"]
    st.markdown(f"**文献：{len(dfp)} 条**")
    st.dataframe(dfp[["基因", "PMID", "年份", "期刊", "标题"]], use_container_width=True)

if "llm" in res:
    dfl = res["llm"]
    st.markdown(f"**LLM 结论：{len(dfl)} 条**")
    bad = int((dfl["溯源校验"] != "通过").sum()) if len(dfl) else 0
    if bad:
        st.warning(f"{bad} 条引用了不存在的 PMID")
    else:
        st.success("全部结论 PMID 校验通过")
    st.dataframe(dfl, use_container_width=True)
    st.download_button("下载结论", dfl.to_csv(index=False).encode("utf-8-sig"),
                       "llm_summaries.csv", "text/csv")
