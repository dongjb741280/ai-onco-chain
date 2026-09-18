"""结构化决策层：从指南抽取「推荐决策」记录（多指南），并做确定性跨指南冲突检测。

- CSCO：决策表确定性解析（表头 Ⅰ/Ⅱ/Ⅲ级推荐，首列可选 分层/治疗阶段）。
- CACA：叙述型，LLM 按小节结构化抽取（无原生等级，LLM 直接给规范强度）。
- diff：按 (治疗阶段, 人群, 分层条件) 匹配，强推荐方案集无重叠 → 冲突。

规范等级归一化仅用于跨指南 diff；报告保留各指南原生等级（见 .scratch/multi-guide/spec.md）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config
from schemas import GuidelineConflict, RecommendationDecision, RecommendationDecisionList

# 规范等级归一化（推荐等级→推荐强度；证据类别→证据等级）
_STRENGTH_BY_GRADE = {"Ⅰ": "强", "Ⅱ": "条件", "Ⅲ": "不足", "I": "强", "II": "条件", "III": "不足"}
_EVIDENCE_LEVEL_BY_EVIDENCE = {"1A": "高", "1B": "高", "2A": "中", "2B": "中", "3": "低"}

_EVIDENCE_RE = re.compile(r"\[(1A|1B|2A|2B|3)\]")
_PAGE_RE = re.compile(r"Page\s+(\d+)")
_GRADE_CELL_RE = re.compile(r"(Ⅰ|Ⅱ|Ⅲ|I|II|III)级推荐")

_STAGE_BY_SECTION = {"二": "新辅助", "三": "辅助", "四": "晚期解救"}


def csco_to_canonical(grade: str | None, evidence: str | None) -> tuple[str | None, str | None]:
    return (
        _STRENGTH_BY_GRADE.get(grade) if grade else None,
        _EVIDENCE_LEVEL_BY_EVIDENCE.get(evidence) if evidence else None,
    )


def _norm_grade(g: str) -> str:
    return {"I": "Ⅰ", "II": "Ⅱ", "III": "Ⅲ"}.get(g, g)


def _detect_population(heading: str) -> str | None:
    if re.search(r"HER-?2\s*阳性", heading):
        return "HER2+"
    if "低表达" in heading:
        return "HER2低表达"
    if "三阴" in heading:
        return "三阴"
    if "内分泌" in heading or "激素受体阳性" in heading:
        return "HR+"
    return None


def _clean_regimen(seg: str) -> str:
    s = seg.strip()
    s = re.sub(r"^[\d²³¹\.、\s]+", "", s)  # 去前导编号/上标/空白
    s = re.sub(r"[\s²³¹]+$", "", s)          # 去尾部上标/空白
    return s.strip(" .,;、。：")


def _split_cell(cell: str) -> list[tuple[str, str | None]]:
    """把一个方案单元格切成 [(方案, 证据类别)]；无证据标记则整格作一个方案。"""
    cell = cell.strip()
    if not cell:
        return []
    markers = list(_EVIDENCE_RE.finditer(cell))
    if not markers:
        reg = _clean_regimen(cell)
        return [(reg, None)] if reg else []
    out = []
    prev_end = 0
    for m in markers:
        reg = _clean_regimen(cell[prev_end:m.start()])
        if reg:
            out.append((reg, m.group(1)))
        prev_end = m.end()
    return out


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    cells = [c for c in _split_row(line) if c != ""]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def parse_csco(md_text: str) -> list[RecommendationDecision]:
    """解析 CSCO 决策表（二/三/四章：新辅助/辅助/晚期解救）为推荐决策记录。"""
    lines = md_text.split("\n")
    records: list[RecommendationDecision] = []
    stage = None
    population = None
    page = None

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]

        m = _PAGE_RE.search(line)
        if m:
            page = int(m.group(1))

        m = re.match(r"^#\s+([一二三四五六七八九十]+)、", line)
        if m:
            stage = _STAGE_BY_SECTION.get(m.group(1))
            population = None
            i += 1
            continue

        if line.startswith("#"):
            p = _detect_population(line)
            if p:
                population = p
            i += 1
            continue

        # 决策表：表头含「级推荐」列，且后跟分隔行
        if line.lstrip().startswith("|") and i + 1 < n and _is_separator(lines[i + 1]):
            header = _split_row(line)
            grade_cols = [j for j, c in enumerate(header) if _GRADE_CELL_RE.search(c)]
            label_col = 0 if header and header[0] in ("分层", "治疗阶段") else None
            if not grade_cols or (len(grade_cols) < 2 and label_col is None):
                i += 1  # 非决策表（如推荐等级图例）
                continue
            j = i + 2
            while j < n and lines[j].lstrip().startswith("|"):
                if _is_separator(lines[j]):
                    j += 1
                    continue
                cells = _split_row(lines[j])
                stratum = cells[label_col].strip() or None if label_col is not None else None
                for gc in grade_cols:
                    if gc >= len(cells):
                        continue
                    gm = _GRADE_CELL_RE.search(header[gc])
                    grade = _norm_grade(gm.group(1)) if gm else None
                    for reg, ev in _split_cell(cells[gc]):
                        strength, ev_lvl = csco_to_canonical(grade, ev)
                        records.append(RecommendationDecision(
                            guide="CSCO",
                            stage=stage,
                            population=population,
                            stratum=stratum,
                            regimen=reg,
                            grade=grade,
                            evidence=ev,
                            page=page,
                            strength=strength,
                            evidence_level=ev_lvl,
                        ))
                j += 1
            i = j
            continue

        i += 1
    return records


def _key(r: RecommendationDecision) -> tuple[str, str, str]:
    return (r.stage or "", r.population or "", r.stratum or "")


def diff(records: list[RecommendationDecision]) -> list[GuidelineConflict]:
    """确定性跨指南冲突：同 (治疗阶段,人群,分层条件) 下两指南强推荐方案集无重叠 → 冲突。

    注意：方案名精确匹配，指南间命名差异（如 TCbHP vs 双靶）会带来噪声；v1 仅作信号，
    裁决交人工（issue 04）。
    """
    by_key: dict[tuple, list[RecommendationDecision]] = {}
    for r in records:
        by_key.setdefault(_key(r), []).append(r)

    conflicts: list[GuidelineConflict] = []
    for key, recs in sorted(by_key.items()):
        csco = [r for r in recs if r.guide == "CSCO"]
        caca = [r for r in recs if r.guide == "CACA"]
        if not (csco and caca):
            continue
        csco_regs = {r.regimen for r in csco if r.strength == "强"} or {r.regimen for r in csco}
        caca_regs = {r.regimen for r in caca if r.strength == "强"} or {r.regimen for r in caca}
        if csco_regs.isdisjoint(caca_regs):
            conflicts.append(GuidelineConflict(
                key=" / ".join(x for x in key if x) or "(未分类)",
                description="强推荐方案无重叠（精确名匹配）",
                csco_regimens=sorted(csco_regs),
                caca_regimens=sorted(caca_regs),
            ))
    return conflicts


def resolve_conflicts(
    conflicts: list[GuidelineConflict],
    profiles: list | None = None,
    strategy: str | None = None,
) -> list[GuidelineConflict]:
    """按策略给每条冲突填裁决：human=人工裁决；china-first=中国指南优先；latest-first=最新优先。

    同优先级（当前 CSCO/CACA 同为 china/2026）按 profiles 顺序 tie-break。
    """
    profiles = profiles or config.GUIDE_PROFILES
    strategy = strategy or config.CONFLICT_STRATEGY
    order = [p.name for p in profiles]
    prof = {p.name: p for p in profiles}

    def pick(names: list[str]) -> str | None:
        return min(names, key=lambda g: order.index(g)) if names else None

    for c in conflicts:
        guides = [g for g in ("CSCO", "CACA")
                  if (c.csco_regimens if g == "CSCO" else c.caca_regimens)]
        if strategy == "china-first":
            china = [g for g in guides if prof[g].region == "china"]
            winner = pick(china or guides)
        elif strategy == "latest-first":
            newest = max((prof[g].year for g in guides), default=None)
            winner = pick([g for g in guides if prof[g].year == newest])
        else:
            winner = None
        c.resolution = f"采用 {winner}" if winner else "人工裁决"
    return conflicts


# ---------- CACA LLM 抽取（叙述型，无原生等级） ----------

# (小节编号, 治疗阶段, 人群提示)；人群提示非 None 时若 LLM 留空则回填
_CACA_SECTIONS = [
    ("10.1.2", "辅助", None),      # 辅助化疗：全人群
    ("10.1.3", "辅助", "HR+"),     # 辅助内分泌
    ("10.1.4", "辅助", "HER2+"),   # 辅助抗HER2
    ("10.2.4", "新辅助", None),    # 新辅助实施：全人群
    ("10.3.1", "晚期解救", "HR+"), # HR+/HER2- 晚期
    ("10.3.2", "晚期解救", "三阴"), # 三阴晚期
]

_CACA_SYSTEM = """你是 CACA 指南结构化抽取助手。从给定小节抽取「推荐决策」记录——该节明确推荐的具体治疗方案。

每条记录字段：
- guide：固定 'CACA'
- stage：固定 '{stage}'
- regimen：方案名（如 AC-T / T-DM1 / CDK4/6抑制剂+内分泌 / 双靶）
- population：适用人群（HER2+/三阴/HR+/HER2低表达），无则留空
- stratum：分层条件（如 高危/non-pCR/绝经前/一线/二线），无则留空
- strength：规范推荐强度（强/条件/不足）。判定：明确「推荐/首选/标准」→强；「可考虑/可选择/可选」→条件；「不推荐/避免」→不足
- grade/evidence/evidence_level/page：一律留空

要求：只抽明确的治疗推荐，忽略检查/分期/随访/病理等非治疗内容；同一方案在不同人群/分层下的不同强度拆成多条。"""


def _extract_caca_sections(md_text: str) -> list[tuple[str, str, str, str]]:
    """按 _CACA_SECTIONS 切出 (stage, pop_hint, num, text)。"""
    lines = md_text.split("\n")
    starts: dict[str, int] = {}
    want = {s[0] for s in _CACA_SECTIONS}
    for i, ln in enumerate(lines):
        m = re.match(r"^####\s+(\d+\.\d+\.\d+)", ln)
        if m and m.group(1) in want:
            starts[m.group(1)] = i
    out = []
    for num, stage, pop_hint in _CACA_SECTIONS:
        start = starts.get(num)
        if start is None:
            continue
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if re.match(r"^#{3,4}\s", lines[j]):
                end = j
                break
        out.append((stage, pop_hint, num, "\n".join(lines[start:end])))
    return out


def extract_caca(md_text: str, llm_ask=None) -> list[RecommendationDecision]:
    """对 10.1/10.2/10.3 的推荐子节逐个做 LLM 结构化抽取，返回带 CACA 身份的推荐决策。"""
    from nodes import _ask  # 惰性导入：避免 parse_csco/diff 依赖 langchain
    ask = llm_ask or _ask

    records: list[RecommendationDecision] = []
    for stage, pop_hint, num, text in _extract_caca_sections(md_text):
        system = _CACA_SYSTEM.format(stage=stage)
        human = f"【小节】{num}　治疗阶段={stage}　人群提示={pop_hint or '待定'}\n\n【指南文本】\n{text}"
        result = ask(RecommendationDecisionList, system, human)
        for r in result.records:
            r.guide = "CACA"
            r.stage = stage
            r.grade = None
            r.evidence = None
            if pop_hint and not r.population:
                r.population = pop_hint
            records.append(r)
    return records


# ---------- CLI ----------

def _load_or_extract_caca(md_text: str, cache_path: Path, llm_ask=None) -> list[RecommendationDecision]:
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return [RecommendationDecision(**d) for d in data]
    records = extract_caca(md_text, llm_ask=llm_ask)
    cache_path.write_text(
        json.dumps([r.model_dump() for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return records


def main() -> None:
    csco_md = config.GUIDE_PROFILES[0].path.read_text(encoding="utf-8")
    caca_md = config.GUIDE_PROFILES[1].path.read_text(encoding="utf-8")

    csco = parse_csco(csco_md)
    caca = _load_or_extract_caca(caca_md, config.OUTPUT_DIR / "caca_decisions.json")

    print(f"CSCO 推荐决策：{len(csco)} 条")
    print(f"CACA 推荐决策：{len(caca)} 条")

    conflicts = resolve_conflicts(diff(csco + caca))
    print(f"冲突：{len(conflicts)} 条（策略={config.CONFLICT_STRATEGY}）")
    for c in conflicts[:20]:
        print(f"  [{c.key}] CSCO={c.csco_regimens}  vs  CACA={c.caca_regimens} → {c.resolution}")


if __name__ == "__main__":
    main()
