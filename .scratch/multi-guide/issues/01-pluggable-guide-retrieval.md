Type: task
Status: resolved

## Question

把 `langgraph_diagnosis` 的指南层从单指南解耦为多指南，让 CACA 进线。

改动点：

1. `config.py`：`GUIDE_PATH` 由单个 `Path` 改为 `GUIDE_PROFILES: list[GuidelineProfile]`。
   `GuidelineProfile` 至少含 `name`（如 `CSCO` / `CACA`）、`path`、`citation_prefix`（引用显示名）。
   首版先配 CSCO + CACA 两个 profile。
2. `guide_rag.py`：`GuideRetriever` 改为对每个 profile 建索引；`retrieve_with_sources` 结果带
   `guide` 字段；`build_query` 去掉 CSCO 专属措辞，改为指南无关的通用 query 构造。
3. `nodes.py`：`_guide_block_with_sources` 与报告节点的来源标注带上指南名（如 `[CSCO·二·P031]` / `[CACA·10.3]`）。
   `trace_chain_node` 的 A→U 骨架保持（属「决策链骨架」层，指南无关，见 spec）。
4. `schemas.py`：报告免责声明与来源引用字段由写死「CSCO」改为「依所选指南」。

## 验收

`python main.py REAL-006 -o reports/REAL-006.md` 产出的报告中，能同时出现 CSCO 与 CACA 两种来源标注。

## Answer

已完成，改动 6 文件：

- `config.py`：`GUIDE_PATH` → `GUIDE_PROFILES: list[GuidelineProfile]`（name/path/citation_prefix），配 CSCO + CACA。
- `guide_rag.py`：`GuideRetriever` 按 profile 逐份建索引（`_retrievers[name]`）；`retrieve_with_sources` 结果带 `guide` 字段；`build_query` 去掉「诊疗指南」标题措辞。
- `nodes.py`：`_guide_block_with_sources` 来源标注加指南名；报告引用示例改为 `[CSCO · …]` / `[CACA · …]`；`trace_chain_node` 的「CSCO 决策链」→「决策链」（A→U 骨架指南无关，见 spec）。
- `schemas.py`：报告免责声明「CSCO 指南」→「所选指南」。
- `render.py`：章节标题「对照 CSCO 分子分型」→「对照指南」。
- `smoke_test.py`：适配 `r.profiles`。

验证：

- `smoke_test.py` 通过：`guides=['CSCO','CACA']`，命中 12 段（每指南 6）。
- `retrieve_with_sources` 分指南计数 `{'CSCO': 6, 'CACA': 6}`。
- 验收：`main.py REAL-006 -o reports/REAL-006.md` 报告出现 `[CSCO · …]` ×4、`[CACA · …]` ×12 两种来源标注。

未决：每指南各取 top_k=6，报告节点上下文由 6 段增至 12 段，prompt 长度/费用翻倍——是否收紧到「每指南 top_k 平分总量」留到 issue 02 一并定。
