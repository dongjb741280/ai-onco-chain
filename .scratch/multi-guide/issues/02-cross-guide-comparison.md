Type: task
Status: resolved

## Question

报告加「跨指南对比」小节：对当前病例涉及的诊疗决策点，并列呈现 CSCO 与 CACA 各自立场，冲突处高亮「⚠ 冲突」，默认不自动裁决。

改动点：

1. `schemas.py`：新增 `GuidelineComparisonEntry`（topic/csco/caca/conflict）+ `GuidelineComparisonList` 包装；`DiagnosisState` 加 `guide_comparison`。
2. `nodes.py`：新增 `compare_guides_node`——按 guide 分组 `guide_sources`，结合 subtype/staging/chain，让 LLM 逐决策点产出对比；一方未提及 ≠ 冲突。
3. `graph.py`：`trace_chain → compare_guides → write_report`。
4. `render.py`：渲染「跨指南对比」小节。
5. `main.py`：`--json` 输出加 `guide_comparison`。

## 验收

`python main.py REAL-006 -o reports/REAL-006.md --thread REAL-006-issue02` 报告出现「跨指南对比」小节，条目含 CSCO/CACA 立场与冲突标注。

## Answer

已完成，改动 5 文件：

- `schemas.py`：`GuidelineComparisonEntry`（topic/csco/caca/conflict）+ `GuidelineComparisonList`；`DiagnosisState.guide_comparison`。
- `nodes.py`：`compare_guides_node`——按 guide 分组 `guide_sources`，结合 subtype/staging/chain，LLM 逐决策点产出对比。
- `graph.py`：`trace_chain → compare_guides → write_report`。
- `render.py`：`_render_guide_comparison` 渲染「跨指南对比（CSCO vs CACA）」小节，`conflict=true` 时标「⚠ 冲突」。
- `main.py`：`--json` 输出加 `guide_comparison`。

验证：

- `smoke_test.py` 通过，图节点含 `compare_guides`。
- `main.py REAL-006 --thread REAL-006-issue02` 报告出现「跨指南对比」小节，6 条决策点各含 CSCO/CACA 立场。
- `conflict=true` 渲染「⚠ 冲突」经合成条目验证通过。

观察：REAL-006 本轮检索的 top-6 片段在相同决策点上多为「一方未提及」，未出现明确冲突——检索式对比受限于「各指南 top-6 不一定对齐同一决策点」，确定性冲突检测需结构化决策层（issue 03）支撑。
