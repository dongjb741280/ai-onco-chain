"""Pydantic 模型：结构化输出（LLM 判断结果）＋ 图状态。

结构化输出 = 把 skill 里的「判读规则/红线/报告模板」变成强类型字段，
LLM 用 with_structured_output 生成，下游可校验、可对照金标准评测。
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


# ---------- 结构化输出 ----------

class MolecularSubtype(BaseModel):
    """分子分型判读（skill 第三步的 HER2/ER/PR/Ki67 判读规则）。"""
    er: str | None = Field(None, description="ER 原始证据，如 '98%+' / '阴性'；未记录为 None")
    pr: str | None = Field(None, description="PR 原始证据")
    her2: str | None = Field(None, description="HER2 IHC/FISH 原始值，如 'IHC 3+' / 'FISH 扩增' / 'IHC 1+'")
    ki67: str | None = Field(None, description="Ki-67 原始值，如 '30%'")
    fish: str | None = Field(None, description="FISH/ISH 结果，如 '扩增阳性' / '阴性' / None")
    brca: str | None = Field(None, description="BRCA1/2：胚系突变 / 无突变 / 未检测（区分 IHC 散在染色，后者≠胚系）")
    menopause: str | None = Field(None, description="绝经状态：绝经前 / 绝经后 / 未记录")
    pd_l1_cps: str | None = Field(None, description="PD-L1 CPS 评分（如 CPS≥10）/ 未检测")
    subtype: str = Field(..., description="HER2阳性型 / 三阴型 / Luminal A / Luminal B(HER2-) / Luminal B(HER2+) / HER2低表达")
    is_her2_low: bool = Field(False, description="是否 HER2 低表达（IHC 1+，或 IHC 2+ 且 FISH 阴性）")
    rationale: str = Field(..., description="判读理由，须指回原文证据；未提供≠阴性")
    summary: str = Field("", description="简洁分型摘要（图标题用），如 'ER 98%+ / PR 80%+ / Her-2(0) / Ki67 30%+'；原发/转移灶不一致时突出差异")


class Staging(BaseModel):
    """TNM/分期（区分初始 vs 当前）。"""
    initial_tnm: str | None = Field(None, description="初始分期，如 'cT4N3M0 ⅡIC期' / 'pT2N1M0 ⅡB期'")
    current_tnm: str | None = Field(None, description="当前分期（复发/转移后常 M1/Ⅳ期）")
    m_status: Literal["M0", "M1", "待核实"] = "M0"
    note: str = Field("", description="M 分期可疑未确诊时说明")
    metastasis_sites: list[str] = Field(default_factory=list, description="转移部位列表（肝/骨/脑/肺/淋巴结/肾上腺/胸膜）")
    treatment_line: str | None = Field(None, description="治疗线：一线 / 二线 / 三线及以上 / 待核验")
    metastasis_detail: str | None = Field(None, description="转移部位详情（含子部位），如 '骨（肋骨、胸椎）；脑（小脑、枕叶）；肺；肝'；无则 None")


class RedLineFlag(BaseModel):
    """安全红线（skill「不确定性与红线」）。命中则转人工，不机械往下走。"""
    kind: str = Field("其他", description="红线类型：M待核实 / 下颌病变 / 骨髓抑制 / 脑膜转移 / 内脏危象 / 其他")
    description: str = Field(..., description="红线描述 + 病历证据")
    action: str = Field(..., description="应如何处理（先处理安全性 / 转 CNS MDT / 补活检 / 停）")


class DecisionChainStep(BaseModel):
    """A→U 决策链一步（skill 第五步）。"""
    node: str = Field(..., description="节点 A..U")
    branch: str | None = Field(None, description="分支（分支节点才有），如 '是：M1（肝、骨）'")
    evidence: str = Field(..., description="病历原文证据")


class RedLineList(BaseModel):
    """一次返回全部红线（避免逐条循环导致的重复）。"""
    red_lines: list[RedLineFlag] = Field(default_factory=list)


class TraceSummary(BaseModel):
    """决策链文字追踪头部摘要（skill 第五步的 人群判断 / 治疗当前-既往）。"""
    population: str = Field(..., description="人群判断：符合/不符合/部分符合 <人群:HER2+/HR+/HR−/HER2低表达> + 一句依据")
    treatment_current: str = Field(..., description="当前治疗类别（如 '靶向+内分泌'）；无写 '未记录'")
    treatment_past: str = Field(..., description="既往治疗类别；无写 '未记录'")


class ChainPath(BaseModel):
    """一次返回完整 A→U 决策链路径。"""
    steps: list[DecisionChainStep] = Field(default_factory=list)


class GuidelineComparisonEntry(BaseModel):
    """跨指南对比一条：同一决策点下 CSCO vs CACA 立场。"""
    topic: str = Field(..., description="决策点，如 'HER2+ 新辅助方案'")
    csco: str = Field("未提及", description="CSCO 立场；该指南未覆盖时写「未提及」")
    caca: str = Field("未提及", description="CACA 立场；该指南未覆盖时写「未提及」")
    conflict: bool = Field(False, description="两者明确不一致（方案/推荐等级相反）；一方未提及不算冲突")


class GuidelineComparisonList(BaseModel):
    """一次返回全部跨指南对比条目。"""
    entries: list[GuidelineComparisonEntry] = Field(default_factory=list)


class DiagnosisReport(BaseModel):
    """9 节诊断报告（skill 第四步模板）。"""
    patient_info: str = Field(..., description="患者信息一行")
    main_diagnosis: list[str] = Field(..., description="主要诊断，按主次，带原始病历来源引用")
    molecular_table: str = Field(..., description="病理与分子分型依据（markdown 表格，带病历与指南来源引用）")
    tnm_staging: str = Field(..., description="TNM 分期：初始 → 当前，带原始病历来源引用")
    treatment_timeline: str = Field(..., description="诊疗经过时间轴（markdown 表格）")
    treatment_evaluation: str = Field(..., description="治疗评价对照指南（markdown 表格，带证据等级与来源引用）")
    recommendations: list[str] = Field(..., description="后续建议，每条带指南依据与来源引用（章节+页码）")
    blockers: list[str] = Field(..., description="卡点/待核实")
    disclaimer: str = Field("依据病历与所选指南整理，属临床辅助，最终以主诊医师/MDT 决策为准。")


# ---------- 结构化决策（推荐决策抽取，多指南） ----------

class RecommendationDecision(BaseModel):
    """一条推荐决策 = 一个(分层, 方案)，带指南来源与规范等级（hybrid-kb issue 03 的 7 字段 + 指南来源/规范等级）。"""
    guide: str = Field(..., description="指南来源：CSCO / CACA")
    stage: str | None = Field(None, description="治疗阶段：新辅助 / 辅助 / 晚期解救")
    population: str | None = Field(None, description="人群：HER2+ / HR+ / HR− / HER2低表达 / 三阴 …")
    stratum: str | None = Field(None, description="分层条件，自由文本（pCR / non-pCR …）")
    regimen: str = Field(..., description="方案名，如 TCbHP / T-DM1")
    grade: str | None = Field(None, description="原生推荐等级：Ⅰ/Ⅱ/Ⅲ（CSCO）")
    evidence: str | None = Field(None, description="原生证据类别：1A/1B/2A/2B/3（CSCO）")
    page: int | None = Field(None, description="来源页码")
    strength: str | None = Field(None, description="规范推荐强度：强 / 条件 / 不足")
    evidence_level: str | None = Field(None, description="规范证据等级：高 / 中 / 低")


class GuidelineConflict(BaseModel):
    """跨指南冲突一条：同一 (治疗阶段, 人群, 分层条件) 下两指南立场不一致。"""
    key: str = Field(..., description="匹配键（治疗阶段/人群/分层条件）")
    description: str = Field(..., description="冲突描述")
    csco_regimens: list[str] = Field(default_factory=list)
    caca_regimens: list[str] = Field(default_factory=list)
    resolution: str | None = Field(None, description="裁决结果：人工裁决 / 采用 <指南>")


class RecommendationDecisionList(BaseModel):
    """一次返回多条推荐决策（CACA LLM 抽取用）。"""
    records: list[RecommendationDecision] = Field(default_factory=list)


# ---------- 确定性抽取（代码产出，非 LLM） ----------

class PatientFeatures(BaseModel):
    """从 JSON 确定性抽取的原始证据（skill 第三步字段映射），供 LLM 判断。"""
    gender: str | None = None
    age: int | None = None
    diagnoses: list[str] = Field(default_factory=list)
    pathology_text: str = ""
    tnm_text: str = ""
    treatment_text: str = ""
    imaging_text: str = ""
    labs_text: str = ""
    narrative_text: str = ""


# ---------- 图状态 ----------

class DiagnosisState(TypedDict, total=False):
    case_id: str
    patient_name: str
    patient_path: str
    patient_data: dict[str, Any]
    features: PatientFeatures
    guide_sections: list[str]
    guide_sources: list[dict[str, Any]]
    subtype: MolecularSubtype
    staging: Staging
    red_lines: list[RedLineFlag]
    chain_path: list[DecisionChainStep]
    trace_summary: TraceSummary
    guide_comparison: list[GuidelineComparisonEntry]
    report: DiagnosisReport
    human_decision: str | None
