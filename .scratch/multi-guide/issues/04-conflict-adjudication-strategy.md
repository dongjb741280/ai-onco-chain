Type: task
Status: resolved

## Question

冲突裁决策略抽可配置项：默认人工，可配 中国指南优先 / 最新优先。作用于 issue 03 的确定性冲突检测（`structured_decisions.diff`）。

改动点：

1. `config.py`：`GuidelineProfile` 加 `region`（china/foreign）+ `year`（版本年份）；新增 `CONFLICT_STRATEGY`（human / china-first / latest-first，默认 human）。
2. `schemas.py`：`GuidelineConflict` 加 `resolution` 字段。
3. `structured_decisions.py`：`resolve_conflicts(conflicts, strategy)` 按策略给每条冲突填裁决；`main()` 应用并打印。

## 验收

- `python structured_decisions.py`（默认 human）打印「人工裁决」。
- `CONFLICT_STRATEGY=china-first` / `latest-first` 打印「采用 <指南>」（当前两指南同为 china/2026，tie-break 按 profiles 顺序 → CSCO）。

## Answer

已完成：

- `config.py`：`GuidelineProfile` 加 `region`/`year`；新增 `CONFLICT_STRATEGY`（human / china-first / latest-first，默认 human）。
- `schemas.py`：`GuidelineConflict` 加 `resolution` 字段。
- `structured_decisions.py`：`resolve_conflicts` 按策略填裁决（human=人工裁决；china-first/latest-first 同优先级按 profiles 顺序 tie-break）；`main()` 应用并打印。

验证（1 条冲突「新辅助/三阴」）：
- 默认 human → 「人工裁决」
- `CONFLICT_STRATEGY=china-first` → 「采用 CSCO」
- `CONFLICT_STRATEGY=latest-first` → 「采用 CSCO」

注：当前 CSCO/CACA 同为 china/2026，china-first 与 latest-first 结果相同（tie-break 到 CSCO）；策略真正产生区分需引入境外指南（NCCN/SITC）或不同版本年份。
