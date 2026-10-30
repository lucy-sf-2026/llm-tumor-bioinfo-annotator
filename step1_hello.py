# -*- coding: utf-8 -*-
"""
阶段 1：最小可运行页面

运行：
    streamlit run step1_hello.py

这一阶段只做一件事：让页面能打开、能看到标题。
先把地基立住，再往上加东西。
"""

import streamlit as st

# set_page_config 必须是第一个 st 调用，否则会报错
st.set_page_config(page_title="我的生信工具", page_icon="🧬", layout="wide")

st.title("🧬 生物实体注释与文献挖掘工具")

st.caption("ID标准化 → 功能富集 → 文献抓取 → LLM 总结")

st.markdown("""
### 这个工具能做什么

1. **基因 ID 转换**：把基因符号（TP53）换成 Entrez 编号（7157）
2. **富集分析**：看这批基因集中在哪些通路
3. **文献抓取**：从 PubMed 拿摘要和 PMID
4. **LLM 总结**：浓缩成结论，每条都带 PMID

> 左侧还没东西，下一阶段加参数区。
""")

st.divider()

st.info("阶段 1 完成：页面能打开了。改代码保存后，右上角会提示 Rerun。")
