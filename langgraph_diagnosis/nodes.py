"""图节点：确定性节点（读文件/抽取）+ LLM 判断节点（结构化输出）。

每个 LLM 节点 = 一段 prompt（内嵌 skill 里的判读规则/红线/报告模板）+ with_structured_output。
"""
from __future__ import annotations

import json
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

import config
from extractor import extract_features, load_patient
from schemas import (
    ChainPath,
    DiagnosisReport,
    MolecularSubtype,
    RedLineList,
    Staging,
    TraceSummary,
)

# ---------- 工具 ----------

_LLM: ChatAnthropic | None = None


def _llm() -> ChatAnthropic:
    """共享的 LangChain ChatAnthropic 客户端（单例，避免每个节点重复建连接）。"""
    global _LLM
    if _LLM is None:
        kwargs = {
            "model": config.ANTHROPIC_MODEL,
            "temperature": 0,
            "thinking": {"type": "disabled"},  # 网关模型默认扩展思考，会与强制 tool_choice（结构化输出）冲突
        }
        if config.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = config.ANTHROPIC_BASE_URL
        _LLM = ChatAnthropic(**kwargs)
    return _LLM


def _ask(model, system: str, human: str):
    """以 LangChain 消息列表（system + human）调用结构化输出；多轮消息可在此基础上追加历史。"""
    msgs = [SystemMessage(content=system), HumanMessage(content=human)]
    return _llm().with_structured_output(model).invoke(msgs)


def _features_block(f) -> str:
    return "\n".join(
        x for x in [
            f"性别：{f.gender or '未记录'}",
            f"年龄：{f.age or '未记录'}",
            f"诊断：{'、'.join(f.diagnoses) if f.diagnoses else '未记录'}",
            f"病理：\n{f.pathology_text or '（未记录）'}",
            f"TNM/分期线索：{f.tnm_text or '（未记录）'}",
            f"治疗：\n{f.treatment_text or '（未记录）'}",
            f"影像：\n{f.imaging_text or '（未记录）'}",
            f"检验：\n{f.labs_text or '（未记录）'}",
            f"叙事：\n{f.narrative_text or '（未记录）'}",
        ]
    )


def _guide_block(sections: list[str]) -> str:
    return "\n\n---\n\n".join(sections) if sections else "（指南未检索到）"


def _guide_block_with_sources(sources: list[dict]) -> str:
    """把检索到的指南片段连同来源（指南+章节+页码）拼给报告节点，供引用。"""
    if not sources:
        return "（指南未检索到）"
    parts = []
    for i, s in enumerate(sources, 1):
        src = f"【来源{i}】 {s.get('guide', '')}"
        if s.get("section"):
            src += f" · {s['section']}"
        if s.get("page"):
            src += f" · P{s['page']}"
        parts.append(f"{src}\n{s['text']}")
    return "\n\n---\n\n".join(parts)


# ---------- 确定性节点 ----------

def load_patient_node(state: dict[str, Any]) -> dict[str, Any]:
    path = state["patient_path"]
    pd = load_patient(path)
    sp = pd.get("standard_patient", {})
    case_id = sp.get("patient_id") or state.get("case_id", "unknown")
    patient_name = sp.get("patient_name")
    return {"case_id": case_id, "patient_name": patient_name, "patient_data": pd}


def extract_features_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"features": extract_features(state["patient_data"])}


def retrieve_guide_node(state: dict[str, Any]) -> dict[str, Any]:
    from guide_rag import GuideRetriever, build_query
    # 轻量缓存：把 retriever 挂到 state 不合适，这里每次构建（节点内闭包会重复建索引）
    # 生产建议：构建一次，注入节点；demo 用模块级单例
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = GuideRetriever()
    q = build_query(state["features"])
    results = _RETRIEVER.retrieve_with_sources(q)
    return {
        "guide_sections": [r["text"] for r in results],
        "guide_sources": results,
    }


_RETRIEVER = None  # 模块级缓存（避免重复建索引）


# ---------- LLM 判断节点（结构化输出） ----------

def judge_subtype_node(state: dict[str, Any]) -> dict[str, Any]:
    f = state["features"]
    system = """你是乳腺癌分子分型判读助手。依据病历证据 + 指南片段，判读分子分型。

判读规则（务必遵守）：
- HER2 IHC 3+ 或 FISH/ISH 扩增 → HER2 阳性型（IHC 3+ 优先于 FISH：FISH 阴性但 IHC 3+ 仍判阳性）
- HER2 IHC 1+，或 IHC 2+ 且 FISH 阴性 → HER2 低表达型
- HER2 IHC 0 但 ≤10% 浸润癌细胞不完整微弱膜染色 → HER2 超低表达（≠简单阴性）
- ER/PR ≥1% → HR 阳性；ER- PR- HER2- → 三阴；写 Luminal → HR 阳性(Luminal)
- Luminal A：HER2-、ER+、PR 高表达、Ki-67<14%；Luminal B(HER2-)：ER+、PR 低或-、Ki-67 高；Luminal B(HER2+)：HER2+、ER+
- 双侧乳腺 / 原发 vs 转移灶受体不一致时，分开说明，以主导病灶为准
- 未提供 ≠ 阴性：没写就留空/说明「未记录」，绝不默认判阴性
- 生物标志物：BRCA1/2（区分胚系突变 vs IHC 散在染色，后者≠胚系）、绝经状态、PD-L1 CPS；未检测就写「未检测/未记录」
- summary：给出一行简洁分型摘要（图标题用），格式如 'ER 98%+ / PR 80%+ / Her-2(0) / Ki67 30%+'；原发 vs 转移灶不一致时突出差异（如 '原发 FISH+；脑转移灶 HER-2 3+'）"""
    human = f"""【病历证据】
{_features_block(f)}

【指南片段】
{_guide_block(state.get("guide_sections", []))}"""
    return {"subtype": _ask(MolecularSubtype, system, human)}


def judge_staging_node(state: dict[str, Any]) -> dict[str, Any]:
    f = state["features"]
    system = """你是乳腺癌分期助手。区分初始 vs 当前分期，判 M 状态。

规则：
- 初始 = 最早记录；当前 = 最近（复发/转移后常 M1/Ⅳ期）
- OCR 的 MO → M0；术后病理用 ypT/N（如 ypT2N1a）
- 疑似转移但无活检/PET 确认 → m_status=待核实（不要硬定 M0/M1）
- 未提供 ≠ 阴性：T/N 具体数值未记录就写「未记录」，绝不编造（如不能凭空写 pT2、N1）；只写病历明确给出的信息
- 转移部位：列出明确的转移部位（肝/骨/脑/肺/淋巴结/肾上腺/胸膜）；治疗线：M1 时按全身治疗时间轴定一线/二线/三线及以上，时间轴不全写「待核验」
- metastasis_detail：若有转移，给出含子部位的详情，如 '骨（肋骨、胸椎）；脑（小脑、枕叶）；肺；肝'；无转移则留空"""
    human = f"""【病历证据】
{_features_block(f)}"""
    return {"staging": _ask(Staging, system, human)}


_RED_LINE_NEG_MARKERS = (
    "不命中", "无需处理", "无需干预", "不构成", "未出现",
)


def _is_real_red_line(flag) -> bool:
    """丢弃模型把「未命中」也包装成条目的占位输出（如 action=「无需处理」）。"""
    return not any(m in f"{flag.description} {flag.action}" for m in _RED_LINE_NEG_MARKERS)


def check_red_lines_node(state: dict[str, Any]) -> dict[str, Any]:
    f = state["features"]
    subtype = state.get("subtype")
    staging = state.get("staging")
    system = """你是安全红线检查助手。逐条对照下列红线，命中就输出；一条都不命中才返回空列表。

红线清单（按证据判定）：
1. M 分期可疑未确诊：疑似转移但无活检/PET/影像确证（仅诊断名「继发恶性肿瘤」而无病理或影像依据）
2. 下颌/颌骨病变：病历出现「下颌/颌骨」病变，且在使用骨改良药（护骨/双膦酸盐/地舒单抗）背景下，需鉴别骨转移 vs 药物相关颌骨坏死 vs 感染（病历明确写「需鉴别」即命中）
3. 严重骨髓抑制：明确的重度血象下降/粒细胞缺乏/血小板显著降低（须有病历检验证据）
4. 脑膜转移：明确「脑膜转移/软脑膜/鞘内」
5. 内脏危象：快速进展的内脏转移且伴器官功能受损（须有「快速进展」或「器官功能受损」的明确证据；仅有内脏转移本身不算）

要求：
- 逐条对照，只有「有明确病历证据」命中的红线才列出；同一类只列一次
- 未命中的红线绝不输出：不要为「血象正常 / 无下颌病变 / 无脑膜」等未命中情形生成占位条目（如 action=「无需处理」），留空即可
- 反例：血象正常 → 不输出骨髓抑制；无「下颌/颌骨」字样 → 不输出下颌病变"""
    human = f"""【已判结果】分型={subtype.subtype if subtype else '未判'}；M={staging.m_status if staging else '未判'}
【病历证据】
{_features_block(f)}"""
    result = _ask(RedLineList, system, human)
    return {"red_lines": [f for f in result.red_lines if _is_real_red_line(f)]}


def _chain_topology_error(steps, m_status: str | None) -> str | None:
    """确定性校验决策链拓扑（用已判 M 分期做权威信号）；返回错误描述，无错误返回 None。"""
    nodes = [s.node for s in steps]
    has_m1 = "M" in nodes
    if m_status in ("M0", "待核实") and has_m1:
        return f"已判 M={m_status}（早期/待核实），链中不应走 M（M1 路径），应走 D(否)→E"
    if m_status == "M1" and not has_m1:
        return "已判 M=M1，链中必须走 D(是)→M（M1 路径）"
    if nodes and nodes[-1] != "U":
        return "路径必须以 U（长期随访）结束"
    return None


def trace_chain_node(state: dict[str, Any]) -> dict[str, Any]:
    f = state["features"]
    subtype = state.get("subtype")
    staging = state.get("staging")
    human = f"""【已判结果】分型={subtype.subtype if subtype else '未判'}；M={staging.m_status if staging else '未判'}
【病历证据】
{_features_block(f)}"""

    chain_system = """你是乳腺癌决策链（A→U）追踪助手。回溯该病例从初诊到当前的完整路径，
只走实际命中的节点，每个节点给：节点标签 + 走的分支（分支节点才有）+ 病历证据（一句原文/指标）。

决策链节点：A 初诊乳腺癌 / B 影像+病理+分子标志物 / C TNM分期+分子分型 / D M分期有无远处转移 /
E 是否适合新辅助 / F 新辅助方案 / G 直接手术 / H 手术+病理反应 / I pCR还是残余 / J 术后辅助 /
K 强化辅助 / L 放疗+内分泌+抗HER2+免疫 / M 转移灶再活检 / N 评估既往治疗+治疗线+安全性 /
O 序贯全身治疗 / P 特殊转移部位 / Q 骨改良药+局部 / R 脑实质or脑膜 / R1 脑实质局部治疗 /
R2 脑膜治疗 / S 继续系统治疗 / T 疗效评估+毒性+MDT / U 长期随访。

回溯要求（D 是分叉点，两条分支不串）：
- D(否，无远处转移/M0) → E；D(是，确诊有远处转移/M1) → M
- M 分期为「待核实」（疑似转移但未确诊）时：走 D(否)→E（按早期/局部进展期继续），D 分支标签写「否：…待核实」，不要当成 M1 走 M
- 早期(M0)路径（D=否）：新辅助 → E(是)→F→H→I→K→L；直接手术 → E(否)→G→J→L（H/I 仅新辅助后有，直接手术不要走 H/I）
- 复发/转移(M1)路径（D=是）：M→N→O→P→…
- 若病历经历「早期(M0)治疗 → 复发转移(M1)」两段（如诊断含「术后复发转移」）：两段都要完整呈现——先走早期段 A→B→C→D(否)→…→L，再走复发段 D(是)→M→…；不要因为最终是 M1 就省略早期段
- 路径必须以 U（长期随访）结束，不要停在 T
- 分支边标签只写「决策 + 病历证据」（如「是：M1（肺、骨、淋巴结）」「否：直接手术」），不要照抄模板示例里的部位
- 未记录的分支不编造"""
    chain_result = _ask(ChainPath, chain_system, human)
    # 确定性拓扑校验：D 分支与已判 M 分期不一致时，带纠错提示重试（最多 2 次）
    m_status = staging.m_status if staging else None
    chain_human = human
    for _ in range(2):
        err = _chain_topology_error(chain_result.steps, m_status)
        if err is None:
            break
        chain_human = f"{human}\n\n[纠错] 上次路径拓扑有误：{err}。请重新走链。"
        chain_result = _ask(ChainPath, chain_system, chain_human)

    summary_system = """你是乳腺癌病例摘要助手。根据病历证据 + 已判分型，给出：
- population：人群判断，写「符合 <人群> + 一句依据」；人群取 HER2阳性/HR阳性/HR阴性(三阴)/HER2低表达 之一（如「符合 HER2低表达：IHC 1+ 且 FISH 阴性」）
- treatment_current：当前治疗类别（如「靶向+内分泌」），无写「未记录」
- treatment_past：既往治疗类别（如「新辅助化疗→手术→辅助化疗」），无写「未记录」"""
    summary_result = _ask(TraceSummary, summary_system, human)

    return {"chain_path": chain_result.steps, "trace_summary": summary_result}


def write_report_node(state: dict[str, Any]) -> dict[str, Any]:
    f = state["features"]
    subtype = state.get("subtype")
    staging = state.get("staging")
    chain = state.get("chain_path", [])
    chain_txt = "\n".join(f"[{s.node}] {s.branch or ''} → {s.evidence}" for s in chain)
    system = """你是乳腺肿瘤科医生助手，产出一份 9 节综合诊断报告（结构化字段）。

要求：
- 推荐等级写 Ⅰ/Ⅱ/Ⅲ 级，证据类别写 1A/1B/2A/2B/3；治疗评价用 ✓/△/⚠
- 「病理与分子分型依据」「治疗评价」「后续建议」中，凡依据指南的知识点，都要标注知识库来源，格式如「[CSCO · 一、乳腺癌的诊断及检查 · P031]」「[CACA · 10.3 晚期乳腺癌解救性全身治疗]」，来源取自【指南片段】里的【来源N】标注（指南+章节+页码）
- 「主要诊断」「病理与分子分型依据」「TNM 分期」中，凡来自病历的证据，标注原始病历来源，格式如「[病历·病理]」「[病历·影像]」，来源取自【病历证据】里的字段（诊断/病理/TNM/分期/治疗/影像/检验/叙事）
- 不替未记录环节脑补"""
    human = f"""【已判结果】
分型={subtype.subtype if subtype else '未判'}；M={staging.m_status if staging else '未判'}
决策链：\n{chain_txt}

【病历证据】
{_features_block(f)}

【指南片段】
{_guide_block_with_sources(state.get("guide_sources", []))}"""
    return {"report": _ask(DiagnosisReport, system, human)}


# ---------- 人机协同节点（interrupt） ----------

def human_review_node(state: dict[str, Any]) -> dict[str, Any]:
    """红线复核：命中红线时暂停，人工决定 proceed(继续并备注) / stop / revise。"""
    from langgraph.types import interrupt
    decision = interrupt({
        "type": "red_line_review",
        "red_lines": [f.model_dump() for f in state.get("red_lines", [])],
        "hint": "红线命中，请人工复核：proceed=继续但已人工评估 / stop=终止 / revise=补充信息后重跑",
    })
    return {"human_decision": json.dumps(decision, ensure_ascii=False)}


def human_approve_node(state: dict[str, Any]) -> dict[str, Any]:
    """报告终审：报告生成后暂停，人工 approve / revise。"""
    from langgraph.types import interrupt
    decision = interrupt({
        "type": "report_approval",
        "report": state.get("report").model_dump() if state.get("report") else {},
    })
    return {"human_decision": json.dumps(decision, ensure_ascii=False)}
