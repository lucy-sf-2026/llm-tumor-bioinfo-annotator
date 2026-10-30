# -*- coding: utf-8 -*-
"""
Streamlit 骨架：从零搭你那个工具的起点。

运行：
    streamlit run app_starter.py

搭建顺序建议：
    1. 先只放 st.title，确认能跑起来
    2. 加输入区（文本框 / 上传）
    3. 加一个按钮 + 一个结果展示
    4. 把业务代码抽成独立函数（gene_convert.convert / enrich.run / ...）
    5. 加 session_state 防丢、加下载按钮
"""

import pandas as pd
import streamlit as st

# ============ 页面配置（必须第一个 st 调用）============
st.set_page_config(page_title="我的工具", page_icon="🧬", layout="wide")

st.title("🧬 生物实体注释工具")
st.caption("一句话说明这个工具干什么")

# ============ 侧边栏：参数区 ============
with st.sidebar:
    st.header("参数")
    disease = st.text_input("疾病限定词", value="cancer")
    per_gene = st.slider("每个基因抓几篇", 1, 10, 5)

# ============ 主区：输入 ============
genes_text = st.text_area(
    "基因列表（一行一个）",
    "TP53\nEGFR\nKRAS",
    height=150,
)
genes = [g.strip().upper() for g in genes_text.splitlines() if g.strip()]
st.write(f"当前 {len(genes)} 个基因")

# 跨重跑保存结果：没有这句，点下一个按钮结果就没了
if "results" not in st.session_state:
    st.session_state.results = {}

# ============ 按钮区：一行四列 ============
c1, c2 = st.columns(2)
do_ids = c1.button("① ID 转换", use_container_width=True)
do_enrich = c2.button("② 富集分析", use_container_width=True)

# ============ 执行逻辑 ============
if do_ids:
    with st.spinner("查询中..."):
        # TODO: 换成你的函数
        # from gene_convert import convert
        # st.session_state.results["ids"] = convert(genes)
        st.session_state.results["ids"] = pd.DataFrame(
            {"基因": genes, "Entrez ID": ["待实现"] * len(genes)}
        )

if do_enrich:
    with st.spinner("调用接口中..."):
        # TODO: from enrich import run
        # _, sig = run(genes)
        # st.session_state.results["enrich"] = sig
        st.session_state.results["enrich"] = pd.DataFrame(
            {"Term": ["示例条目"], "校正P值(BH)": [0.001]}
        )

# ============ 展示区 ============
if "ids" in st.session_state.results:
    st.subheader("ID 转换结果")
    st.dataframe(st.session_state.results["ids"], use_container_width=True)

if "enrich" in st.session_state.results:
    df = st.session_state.results["enrich"]
    st.subheader(f"富集结果（{len(df)} 条）")
    st.dataframe(df, use_container_width=True)

    # 下载按钮：必须把内容转成 bytes
    st.download_button(
        "下载结果 csv",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name="enrich_results.csv",
        mime="text/csv",
    )
