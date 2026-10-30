# -*- coding: utf-8 -*-
"""
配置中心：系统的"方向"全部定义在这里。

换研究对象（肿瘤→植物/微生物/蛋白…）只改这个文件或切换 profile，
各个业务模块（gene_convert / enrich / batch_pubmed / llm_summarize / app）不需要改。

用法：
    import config
    config.set_profile("mouse_gene")     # 切换
    config.P                             # 当前生效的配置字典

也可以不改代码，用环境变量临时切换：
    $env:BIO_PROFILE="mouse_gene"
"""

import os

# ============================================================
# 各个方向的配置（profile）
# ============================================================
PROFILES = {
    # ---------- 默认：人源肿瘤基因 ----------
    "human_cancer": {
        "name": "人源肿瘤基因",
        "entity_label": "基因",          # 界面上怎么称呼研究对象
        "domain": "肿瘤",                # 提示词里的领域词
        "example_genes": "TP53\nEGFR\nBRCA1\nMYC\nKRAS\nPTEN\nRB1\nCDKN2A",
        "species": "human",
        "id_scopes": "symbol",
        "id_fields": "entrezgene,name,summary,alias",
        "id_column": "Entrez ID",
        "enrichr_libs": {
            "GO_Biological_Process_2023": "GO 生物学过程",
            "KEGG_2021_Human": "KEGG 通路",
            "Reactome_2022": "Reactome 通路",
            "MSigDB_Hallmark_2020": "Hallmark 基因集",
        },
        "pubmed_template": "({name}){disease_part}",
        "pubmed_default_disease": "cancer",
        "enrich_note": "",
    },

    # ---------- 人源基因，不限疾病 ----------
    "human_gene": {
        "name": "人源基因（通用）",
        "entity_label": "基因",
        "domain": "生物医学",
        "example_genes": "TP53\nEGFR\nAKT1\nMTOR\nMAPK1",
        "species": "human",
        "id_scopes": "symbol",
        "id_fields": "entrezgene,name,summary",
        "id_column": "Entrez ID",
        "enrichr_libs": {
            "GO_Biological_Process_2023": "GO 生物学过程",
            "KEGG_2021_Human": "KEGG 通路",
            "Reactome_2022": "Reactome 通路",
        },
        "pubmed_template": "({name}){disease_part}",
        "pubmed_default_disease": "",
        "enrich_note": "",
    },

    # ---------- 小鼠 ----------
    "mouse_gene": {
        "name": "小鼠基因",
        "entity_label": "基因",
        "domain": "生物医学",
        "example_genes": "Trp53\nEgfr\nKras\nPten\nMyc",
        "species": "mouse",
        "id_scopes": "symbol",
        "id_fields": "entrezgene,name",
        "id_column": "Entrez ID",
        "enrichr_libs": {
            "GO_Biological_Process_2023": "GO 生物学过程",
            "KEGG_2019_Mouse": "KEGG 通路（小鼠）",
        },
        "pubmed_template": "({name}) AND (mouse OR mice){disease_part}",
        "pubmed_default_disease": "",
        "enrich_note": "",
    },

    # ---------- 蛋白 ----------
    "protein": {
        "name": "蛋白（基因符号 → UniProt）",
        "entity_label": "蛋白",
        "domain": "蛋白质组学",
        "example_genes": "TP53\nEGFR\nAKT1\nMAPK1",
        "species": "human",
        "id_scopes": "symbol",
        "id_fields": "uniprot,name,entrezgene",
        "id_column": "UniProt ID",
        "enrichr_libs": {
            "GO_Molecular_Function_2023": "GO 分子功能",
            "Reactome_2022": "Reactome 通路",
        },
        "pubmed_template": "({name}) AND (protein){disease_part}",
        "pubmed_default_disease": "",
        "enrich_note": "",
    },

    # ---------- 拟南芥（植物） ----------
    "arabidopsis": {
        "name": "拟南芥基因（植物）",
        "entity_label": "基因",
        "domain": "植物生物学",
        "example_genes": "FT\nSOC1\nAP1\nLFY\nTFL1",
        # mygene 不认 "arabidopsis"，官方别名是 thale-cress（等价于 taxid 3702）
        "species": "thale-cress",
        "id_scopes": "symbol",
        "id_fields": "entrezgene,name",
        "id_column": "Entrez ID",
        # Enrichr 没有植物专用库，这里留空并给出说明
        "enrichr_libs": {},
        "pubmed_template": "({name}) AND (Arabidopsis){disease_part}",
        "pubmed_default_disease": "",
        "enrich_note": "Enrichr 不提供拟南芥专用基因集库。"
                       "ID 标准化和文献检索可用；富集需接入 TAIR / AgriGO / MapMan。",
    },

    # ---------- 代谢物（示意，未接入） ----------
    "metabolite": {
        "name": "代谢物（需外部数据库）",
        "entity_label": "代谢物",
        "domain": "代谢组学",
        "example_genes": "Glucose\nLactate\nGlutamine",
        "species": "human",
        "id_scopes": "symbol",
        "id_fields": "name",
        "id_column": "KEGG 化合物 ID",
        "enrichr_libs": {},
        "pubmed_template": "({name}) AND (metabolite){disease_part}",
        "pubmed_default_disease": "",
        "enrich_note": "代谢物富集需接入 MetaboAnalyst 或 KEGG 化合物库；"
                       "mygene 与 Enrichr 不适用。当前仅支持文献检索。",
    },

    # ---------- 微生物（示意，未接入） ----------
    "microbe": {
        "name": "微生物/菌群（需外部数据库）",
        "entity_label": "菌群",
        "domain": "微生物组学",
        "example_genes": "Bacteroides fragilis\nEscherichia coli\nAkkermansia muciniphila",
        "species": "human",
        "id_scopes": "symbol",
        "id_fields": "name",
        "id_column": "NCBI Taxonomy ID",
        "enrichr_libs": {},
        "pubmed_template": "({name}) AND (microbiome OR microbiota){disease_part}",
        "pubmed_default_disease": "",
        "enrich_note": "菌群富集需接入 SILVA / KEGG 微生物通路；"
                       "当前仅支持文献检索与 LLM 归纳。",
    },
}

DEFAULT_PROFILE = "human_cancer"

_current = os.environ.get("BIO_PROFILE", DEFAULT_PROFILE)


def set_profile(key):
    """切换当前方向。key 必须在 PROFILES 里，否则报错并列出可选值。"""
    global _current
    if key not in PROFILES:
        raise KeyError(f"未知 profile: {key}。可选：{', '.join(PROFILES)}")
    _current = key
    return PROFILES[key]


def current_key():
    return _current


def get(key=None):
    return PROFILES[key or _current]


class _Proxy(dict):
    """让 config.P 始终指向当前 profile，切换后无需重新 import。"""

    def _d(self):
        return PROFILES[_current]

    def __getitem__(self, k):
        return self._d()[k]

    def get(self, k, default=None):
        return self._d().get(k, default)

    def __contains__(self, k):
        return k in self._d()

    def keys(self):
        return self._d().keys()

    def items(self):
        return self._d().items()


# 各模块统一用 config.P["xxx"] 读取
P = _Proxy()


def describe():
    """给界面用：当前方向的一句话说明。"""
    p = PROFILES[_current]
    return f"{p['name']}｜实体：{p['entity_label']}｜物种：{p['species']}"
