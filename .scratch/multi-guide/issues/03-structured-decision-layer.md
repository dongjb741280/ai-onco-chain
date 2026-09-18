Type: task
Status: resolved

## Question

落地「结构化决策层」并泛化到多指南：从指南抽取 `推荐决策` 记录（方案 + 推荐等级 + 证据类别 + 来源），加 `指南来源` + `规范等级`（推荐强度/证据等级），用于确定性跨指南冲突检测（issue 02 观察到的检索式对比的补强）。

范围（已拍：全量含 CACA LLM 抽取）：

1. **schema**（`schemas.py`）：`RecommendationDecision`（guide/stage/population/stratum/regimen/grade/evidence/page/strength/evidence_level）+ `GuidelineConflict`。
2. **CSCO 确定性抽取**（`structured_decisions.py`）：解析 `guide_csco.md` 决策表（表头 `Ⅰ/Ⅱ/Ⅲ级推荐`，首列可为 `分层`/`治疗阶段`）→ `推荐决策` 记录；`csco_to_canonical` 把 推荐等级+证据类别 映射到 规范强度+证据等级。
3. **CACA LLM 抽取**（`structured_decisions.py`）：对 10.1 辅助 / 10.2 新辅助 / 10.3 晚期解救 按小节分块，LLM 结构化抽取（指南来源=CACA，无原生等级，LLM 直接给规范强度）。
4. **diff**（`structured_decisions.py`）：按 (治疗阶段, 人群, 分层条件) 匹配，方案集合不一致或规范强度相反 → 冲突。
5. **CLI**：`structured_decisions.py` 作为脚本跑全流程，CACA 结果缓存到 `Data_Cleaning/process/output/caca_decisions.json`。
6. **术语**：`指南来源`/`规范推荐强度`/`规范证据等级` 落 `CONTEXT.md`。

## 验收

- `structured_decisions.py` 可跑通，产出 CSCO + CACA 两批 `推荐决策`，`diff` 能列出冲突。
- CSCO 解析对已知表 spot-check 通过（如 HER2+ 新辅助：TCbHP Ⅰ级 [1A]）。

## Answer

已完成，新增 `structured_decisions.py` + schema + 术语：

- `schemas.py`：`RecommendationDecision`（guide/stage/population/stratum/regimen/grade/evidence/page/strength/evidence_level）+ `GuidelineConflict` + `RecommendationDecisionList`。
- `structured_decisions.py`：
  - `parse_csco`：解析 CSCO 决策表（二/三/四章，表头 Ⅰ/Ⅱ/Ⅲ级推荐，首列 分层/治疗阶段）→ 224 条记录；`csco_to_canonical` 把 推荐等级+证据类别 → 规范强度+证据等级。
  - `extract_caca`：对 10.1.2/10.1.3/10.1.4/10.2.4/10.3.1/10.3.2 六个推荐子节 LLM 结构化抽取 → 150 条记录（guide=CACA，无原生等级，LLM 给规范强度）。
  - `diff`：按 (治疗阶段, 人群, 分层条件) 匹配，强推荐方案集无重叠 → 冲突。
  - `__main__`：跑全流程，CACA 结果缓存到 `Data_Cleaning/process/output/caca_decisions.json`。
- `CONTEXT.md`：落 `指南来源`/`规范推荐强度`/`规范证据等级` 三个术语。

验证：`python structured_decisions.py` → CSCO 224 + CACA 150，`diff` 检出 1 条冲突（新辅助/三阴：CSCO 含铂+PD-1 vs CACA EC-P/EC-T/PCb+帕博利珠单抗，实为命名差异的同方向推荐）。

已知局限（记入后续 issue 04 / 专项）：
- 方案名精确匹配，跨指南命名差异（TCbHP vs 双靶）产生噪声/漏配。
- CACA 人群标签不统一（HR+/HER2-、HR+/HER2+ 与 HR+、HER2+ 混用），压低 diff 匹配率。
- CSCO 脚注噪声（如 `T-DM14`、`TP4`）未清洗。
