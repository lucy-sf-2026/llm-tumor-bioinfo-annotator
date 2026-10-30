# -*- coding: utf-8 -*-
"""
阶段 2：加输入区（侧边栏参数 + 基因列表）

运行：
    streamlit run step2_input.py

这一阶段学两件事：
    1. with st.sidebar:  左侧参数区
    2. st.text_area()    多行文本输入

注意：这时还没有按钮，但你随便改一下输入框，
页面会立刻重跑并更新 —— 这就是 Streamlit 的工作方式。
"""

import streamlit as st

st.set_page_config(page_title="我的生信工具", page_icon="🧬", layout="wide")

st.title("🧬 生物实体注释与文献挖掘工具（阶段 2：输入区）")

# ============ 侧边栏：参数区 ============
with st.sidebar:
    st.header("参数设置")
    disease = st.text_input("疾病限定词", value="cancer",
                            help="留空则不限定，例如 lung adenocarcinoma")
    per_gene = st.slider("每个基因抓几篇文献", 1, 10, 5)
    st.caption("这些值随时可改，改了页面会立刻重跑")

# ============ 主区：基因输入 ============
st.subheader("① 输入基因列表")

default_genes = "TP53\nEGFR\nBRCA1\nMYC\nKRAS\nPTEN\nRB1\nCDKN2A"
txt = st.text_area("一行一个基因", default_genes, height=180)

# 解析成列表：按行拆、去空、统一大写
genes = [g.strip().upper() for g in txt.replace(",", "\n").splitlines() if g.strip()]

st.write(f"识别到 **{len(genes)}** 个基因：{', '.join(genes)}")

if len(genes) < 2:
    st.warning("至少需要 2 个基因才能做富集分析")
else:
    st.success(f"输入有效，当前疾病限定词：{disease}，每个基因取 {per_gene} 篇")
