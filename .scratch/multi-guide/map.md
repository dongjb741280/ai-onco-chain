# multi-guide map

## Destination

spec 见 `spec.md`：把 `langgraph_diagnosis` 从单指南（CSCO）硬编码解耦为多指南可插拔，
先让 CACA 进线，为 NCCN / SITC / 中国医师协会 留接口。

## Notes

- 现状：`guide_caca.md`（465KB）已产出但未接入流水线；`config.GUIDE_PATH` 只指向 `guide_csco.md`；
  `nodes.trace_chain_node` 写死 CSCO 的 A→U 决策链拓扑。
- 顺延 hybrid-kb，非推翻：hybrid-kb map 里的「多指南 out of scope」在本 effort 解除。
- 每 session consult：`grilling` + `domain-modeling`（`指南来源` / `规范推荐强度` / `规范证据等级` 术语需定稿，落到 `CONTEXT.md`）。

## Decisions so far

- [spec 定稿](spec.md)：三层拆分——临床事实/安全（指南无关）+ 决策链骨架（指南无关）+ 推荐内容（指南相关，唯一可插拔）。
- 路线 = A 检索融合起步、B 统一决策模型留口（`profile.decision_chain` 先 `None`）。
- 规范等级归一化：仅用于跨指南 diff / 冲突检测，报告保留原生等级。
- [指南层可插拔实现](issues/01-pluggable-guide-retrieval.md)：config 多指南 + GuideRetriever 多索引 + 引用带指南名，CACA 进线（REAL-006 报告已见 CSCO×4 / CACA×12 引用）。

## Not yet specified

- 冲突裁决策略的默认值（默认人工；可选「中国指南优先 / 最新优先」，待定）。

## Out of scope

- 多癌种；自动裁决冲突；统一决策模型 B 本轮实现。
