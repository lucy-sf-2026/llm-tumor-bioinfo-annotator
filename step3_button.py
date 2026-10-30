# -*- coding: utf-8 -*-
"""
阶段 3：加按钮 + 结果展示（先用假数据）

运行：
    streamlit run step3_button.py

这一阶段是整个页面最关键的一步，学三件事：
    1. st.button()      点击才执行
    2. st.session_state 跨重跑保存结果（不写这句，结果会消失）
    3. st.dataframe()   展示表格

为什么先不接真实接口？
    因为界面逻辑和业务逻辑要分开调。
    界面跑通了再接真函数，出了问题才知道是哪一层的错。
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="我的生信工具", page_icon="🧬", layout="wide")
st.title("🧬 生物实体注释与文献挖掘工具（阶段 3：按钮与状态）")

with st.sidebar:
    st.header("参数设置")
    disease = st.text_input("疾病限定词", value="cancer")

st.subheader("① 输入基因列表")
default_genes = "TP53\nEGFR\nBRCA1\nKRAS"
genes = [g.strip().upper()
         for g in st.text_area("一行一个基因", default_genes, height=150)
         .replace(",", "\n").splitlines() if g.strip()]
st.write(f"识别到 **{len(genes)}** 个基因")

# ========== 关键：跨重跑保存结果 ==========
if "results" not in st.session_state:
    st.session_state.results = {}

st.subheader("② 执行")

col1, col2 = st.columns(2)
run_ids = col1.button("基因 ID 转换", use_container_width=True)
run_enrich = col2.button("富集分析", use_container_width=True)

# ---- 按钮 1：假数据 ----
if run_ids:
    with st.spinner("查询中..."):
        st.session_state.results["ids"] = pd.DataFrame({
            "基因": genes,
            "Entrez ID": [f"假ID{i}" for i in range(len(genes))],
            "是否找到": "是",
        })

# ---- 按钮 2：假数据 ----
if run_enrich:
    with st.spinner("计算中..."):
        st.session_state.results["enrich"] = pd.DataFrame({
            "Term": ["Negative Regulation Of Cell Cycle",
                     "p53 Pathway",
                     "E2F Targets"],
            "校正P值(BH)": [3.42e-06, 3.72e-04, 1.38e-05],
            "重叠基因数": [4, 3, 4],
        })

# ========== 展示区：读 session_state ==========
st.subheader("③ 结果")

if "ids" in st.session_state.results:
    st.markdown("**ID 转换结果**")
    st.dataframe(st.session_state.results["ids"], use_container_width=True)
else:
    st.info("还没点「基因 ID 转换」")

if "enrich" in st.session_state.results:
    df = st.session_state.results["enrich"]
    st.markdown(f"**富集结果（{len(df)} 条）**")
    st.dataframe(df, use_container_width=True)

    st.download_button(
        "下载 csv",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name="enrich_results.csv",
        mime="text/csv",
    )
else:
    st.info("还没点「富集分析」")

st.divider()
st.caption("试试：点按钮 → 出结果 → 改上面的基因列表 → 结果还在吗？在，因为存进了 session_state。")
