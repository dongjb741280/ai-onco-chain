"""把结构化结果渲染成与 diagnosis-report skill 一致的 markdown 输出。

skill 产出两样：① 9 节综合诊断报告 ② A→U 决策链文字追踪。
这里把 LangGraph 的结构化结果（report / chain_path / subtype / staging）还原成同一格式。
"""
from __future__ import annotations

NODE_LABELS = {
    "A": "初诊乳腺癌",
    "B": "影像 + 病理 + 分子标志物",
    "C": "TNM 分期 + 分子分型与风险分层",
    "D": "M 分期：有无远处转移？",
    "E": "是否适合新辅助治疗？",
    "F": "按分子亚型选择新辅助方案",
    "G": "直接手术与腋窝评估",
    "H": "手术 + 病理反应评估",
    "I": "pCR 还是残余病灶？",
    "J": "按风险完成术后辅助治疗",
    "K": "强化辅助",
    "L": "放疗 / 内分泌 / 抗HER2 / 免疫",
    "M": "转移灶再活检与再分型",
    "N": "评估既往治疗、耐药、治疗线、安全性",
    "O": "按分子亚型序贯全身治疗",
    "P": "特殊转移部位？",
    "Q": "骨改良药 + 局部放疗/手术评估",
    "R": "脑转移：脑实质 or 脑膜？",
    "R1": "脑实质转移局部治疗",
    "R2": "脑膜转移治疗",
    "S": "继续系统治疗与疗效评估",
    "T": "疗效评估、毒性管理、MDT",
    "U": "长期随访、复发监测",
}


# 决策链全图节点（mermaid，完整标签；菱形 = D/E/I/P/R）
_NODE_DEFS = {
    "A": "A[初诊乳腺癌]",
    "B": "B[影像 + 病理 + 分子标志物<br/>（ER/PR/HER2/Ki67/FISH、BRCA1/2、PD-L1 CPS、绝经）]",
    "C": "C[TNM分期 + 分子分型与风险分层<br/>HER2阳性 / 低表达 / 超低表达 / 三阴性 / HR阳性]",
    "D": "D{M分期：有无远处转移?}",
    "E": "E{是否适合新辅助治疗?}",
    "F": "F[按分子亚型选择新辅助方案<br/>HER2+双靶 / 三阴 TP-AC+PD-1（BRCA含铂）/ HR+内分泌]",
    "G": "G[直接手术与腋窝评估]",
    "H": "H[手术 + 病理反应评估]",
    "I": "I{pCR还是残余病灶?}",
    "J": "J[按风险完成术后辅助治疗]",
    "K": "K[强化辅助（HER2+/三阴）<br/>T-DM1 / T-DXd / 卡培他滨 / 奥拉帕利（BRCA）/ PD-1至满1年]",
    "L": "L[放疗 / 内分泌（绝经前OFS+AI / 绝经后AI+CDK4/6i）<br/>抗HER2 / 免疫]",
    "M": "M[转移灶再活检与再分型]",
    "N": "N[评估既往治疗、耐药、疾病速度、治疗线、安全性]",
    "O": "O[按分子亚型序贯全身治疗<br/>HER2阳性 / 低表达/超低表达（T-DXd）<br/>三阴（PD-1 CPS / PARP BRCA）/ HR+（CDK4/6i）]",
    "P": "P{特殊转移部位?}",
    "Q": "Q[骨改良药 + 局部放疗/手术评估]",
    "R": "R{脑转移：脑实质 or 脑膜?}",
    "R1": "R1[脑实质转移：SRS / FSRT / 手术 / 全脑放疗]",
    "R2": "R2[脑膜转移：全中枢放疗 / 鞘内注射]",
    "S": "S[继续系统治疗与疗效评估]",
    "T": "T[疗效评估、毒性管理、营养/心理支持、生活质量与MDT]",
    "U": "U[长期随访、复发监测与临床研究/真实世界证据更新]",
}

# 决策链 28 条边（顺序即 linkStyle 下标 0-27）；branch_node = 可被病历分支证据覆盖的分支节点
_EDGES = [
    ("A", "B", None, None),
    ("B", "C", None, None),
    ("C", "D", None, None),
    ("D", "E", "否：M0 早期/局部进展期", "D"),
    ("E", "F", "是", "E"),
    ("E", "G", "否", "E"),
    ("F", "H", None, None),
    ("G", "J", None, None),
    ("H", "I", None, None),
    ("I", "J", "pCR", "I"),
    ("I", "K", "non-pCR", "I"),
    ("J", "L", None, None),
    ("K", "L", None, None),
    ("D", "M", "是：M1 复发/转移期", "D"),
    ("M", "N", None, None),
    ("N", "O", None, None),
    ("O", "P", None, None),
    ("P", "Q", "骨转移", "P"),
    ("P", "R", "脑转移", "P"),
    ("P", "S", "其他内脏/软组织转移", "P"),
    ("R", "R1", "脑实质", "R"),
    ("R", "R2", "脑膜", "R"),
    ("L", "T", None, None),
    ("Q", "T", None, None),
    ("R1", "T", None, None),
    ("R2", "T", None, None),
    ("S", "T", None, None),
    ("T", "U", None, None),
]

# 分支节点 → 其出边下标（用于把病历分支证据只放到「实际走过的那条边」上）
_BRANCH_OUT = {"D": [3, 13], "E": [4, 5], "I": [9, 10], "P": [17, 18, 19], "R": [20, 21]}


def _mmd_escape(s: str) -> str:
    return s.replace("|", "/").replace('"', "'").replace("\n", " ")


def render_decision_chain_mmd(result: dict) -> str:
    """按 skill 第六步，生成高亮决策链 mermaid 源码（.mmd）。"""
    subtype = result.get("subtype")
    staging = result.get("staging")
    chain = result.get("chain_path", [])
    case = result.get("case_id", "")

    visited = {s.node for s in chain}
    if "U" in visited:
        visited.add("T")  # 汇合到 T 才到 U；LLM 常省略 T，桥接

    # 标题节点：病例 + 分型/IHC + 分期/转移部位
    head = str(case or "未知病例")
    if subtype and subtype.subtype:
        ev = " ".join(f"{k} {v}" for k, v in (("ER", subtype.er), ("PR", subtype.pr), ("HER2", subtype.her2), ("Ki67", subtype.ki67)) if v)
        head += f"：{subtype.subtype}" + (f"（{ev}）" if ev else "")
    tail = []
    if staging:
        tnm = staging.current_tnm or staging.initial_tnm or staging.m_status
        if tnm:
            tail.append(tnm)
        if staging.metastasis_sites:
            tail.append("、".join(staging.metastasis_sites) + "转移")
    title = "<br/>".join(x for x in [head, " ".join(tail)] if x)

    branch_by_node = {s.node: s.branch for s in chain if s.branch}
    # 覆盖分支边标签：仅当该分支节点只有一条出边被走过（避免两段式病例误标）
    overrides: dict[int, str] = {}
    for bn, idxs in _BRANCH_OUT.items():
        hit = [i for i in idxs if _EDGES[i][1] in visited]
        if len(hit) == 1 and bn in branch_by_node:
            overrides[hit[0]] = _mmd_escape(branch_by_node[bn])

    L: list[str] = []
    L.append("flowchart TD")
    L.append(f'TITLE["{title}"]')
    L.append("classDef caption fill:#fff,stroke:none,color:#111827,font-weight:bold;")
    L.append("classDef path fill:#fca5a5,stroke:#dc2626,color:#7f1d1d,stroke-width:3px;")
    L.append("classDef dim fill:#f3f4f6,stroke:#d1d5db,color:#9ca3af,stroke-width:1px;")
    L.append("")
    L.extend(_NODE_DEFS.values())
    L.append("")
    for i, (u, v, label, _bn) in enumerate(_EDGES):
        if i in overrides:
            label = overrides[i]
        if label:
            L.append(f"{u} -->|{label}| {v}")
        else:
            L.append(f"{u} --> {v}")
    L.append("")
    for node in _NODE_DEFS:
        cls = "path" if node in visited else "dim"
        L.append(f"class {node} {cls};")
    L.append("class TITLE caption;")
    L.append("")
    for i, (u, v, _label, _bn) in enumerate(_EDGES):
        traversed = u in visited and v in visited
        style = "stroke:#dc2626,stroke-width:3px" if traversed else "stroke:#d1d5db,stroke-width:1px"
        L.append(f"linkStyle {i} {style};")
    L.append("")
    L.append("TITLE ~~~ A")  # 隐形边置顶，声明在所有边之后，linkStyle 下标不错位
    return "\n".join(L)


def render_diagnosis(result: dict) -> str:
    f = result.get("features")
    name = result.get("patient_name") or result.get("case_id", "")
    subtype = result.get("subtype")
    staging = result.get("staging")
    report = result.get("report")
    chain = result.get("chain_path", [])

    L: list[str] = []
    # ── 报告 ──
    L.append("# 乳腺癌综合诊断报告\n")
    L.append(f"**患者**：{name}　｜　**性别**：{f.gender or '未记录'}　｜　**年龄**：{f.age or '未记录'} 岁\n")
    L.append("## 主要诊断\n" + "\n".join(f"{i}. {d}" for i, d in enumerate(report.main_diagnosis, 1)))
    L.append("\n## 病理与分子分型依据（对照 CSCO 分子分型）\n" + report.molecular_table)
    L.append("\n## TNM 分期\n" + report.tnm_staging)
    L.append("\n## 诊疗经过\n" + report.treatment_timeline)
    L.append("\n## 治疗评价（对照指南）\n" + report.treatment_evaluation)
    L.append("\n## 后续建议\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(report.recommendations, 1)))
    L.append("\n## 卡点 / 待核实\n" + "\n".join(f"- {b}" for b in report.blockers))
    L.append("\n## 说明\n\n> " + report.disclaimer)

    # ── 决策链追踪 ──
    L.append("\n\n---\n\n## 决策链追踪 A→U\n")
    L.append("```")
    L.append(f"病例 {result.get('case_id', '')}：{f.gender or '?'} {f.age or '?'}岁")
    if f.diagnoses:
        L.append(f"诊断：{'、'.join(f.diagnoses)}")
    if staging:
        init = staging.initial_tnm or "未记录"
        cur = staging.current_tnm or staging.m_status
        L.append(f"TNM/分期：{init} → {cur}")
    if subtype:
        ev = "  ".join(f"{k} {v}" for k, v in [("ER", subtype.er), ("PR", subtype.pr), ("HER2", subtype.her2), ("Ki67", subtype.ki67), ("FISH", subtype.fish)] if v)
        L.append(f"分子分型：{subtype.subtype}" + (f"   {ev}" if ev else ""))
        L.append(f"生物标志物：BRCA1/2 {subtype.brca or '未检测'}；绝经 {subtype.menopause or '未记录'}；PD-L1 CPS {subtype.pd_l1_cps or '未检测'}")
    if staging:
        if staging.metastasis_sites:
            L.append(f"转移部位：{'、'.join(staging.metastasis_sites)}")
        if staging.treatment_line:
            L.append(f"治疗线：{staging.treatment_line}")
    L.append("\n决策链路径：")
    for s in chain:
        label = NODE_LABELS.get(s.node, s.node)
        branch = f"  ← {s.branch}" if s.branch else ""
        L.append(f"  [{s.node}] {label}{branch}")
        L.append(f"       ↳ {s.evidence}")
    L.append("\n卡点/待核实：")
    for b in report.blockers:
        L.append(f"  - {b}")
    L.append("```")

    return "\n".join(L)
