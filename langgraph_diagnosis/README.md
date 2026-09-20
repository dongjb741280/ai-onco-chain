# LangGraph 诊疗诊断流程

把 `.claude/skills/diagnosis-report` 的诊疗场景，用 **LangGraph（图编排）+ LlamaIndex（指南 RAG）+ 结构化输出 + 人机协同** 重写为可运行的 Python 流水线。

> 目的不是替换 skill，而是给同一场景一个「可批量、可评测、可生产化」的工程形态。skill 里 80% 的价值——领域红线与证据锚定的 prompt 规则——在这里被原样搬进 prompt，其余「确定性抽取」下沉为代码。

## 与 skill 的步骤映射

| skill 步骤 | 这里的实现 | 类型 |
|---|---|---|
| 第一步 定位读取病历 | `config.resolve_patient_path` + `extractor.load_patient` | 确定性代码 |
| 第二步 读指南章节 | `guide_rag.GuideRetriever`（LlamaIndex 按标题切块 + 语义/关键词检索） | RAG |
| 第三步 抽取特征 | `extractor.extract_features`（字段映射，权威字段 + 叙事兜底） | 确定性代码 |
| 第三步 分子分型/分期/红线判断 | `nodes.judge_subtype / judge_staging / check_red_lines` | LLM 结构化输出 |
| 第四步 诊断报告 | `nodes.write_report`（9 节模板 → `DiagnosisReport`） | LLM 结构化输出 |
| 第五步 决策链 A→U | `nodes.trace_chain`（逐节点回溯 + 证据） | LLM 结构化输出 |
| 红线 + 人机协同 | `graph.route_after_red_lines` 条件边 + `human_review`/`human_approve` 的 `interrupt` | 图编排 + HITL |

## 图结构

```
START → load_patient → extract_features → retrieve_guide
      → judge_subtype → judge_staging → check_red_lines
      → 〔条件边〕 命中红线 → human_review(interrupt) → trace_chain
                  无红线        → trace_chain
      → write_report → human_approve(interrupt) → END
```

- **条件边** = 决策链的关键岔口：红线→人工（`route_after_red_lines`）。M0/M1、pCR/non-pCR、脑实质/脑膜等更细分支，可在 `trace_chain` 内由 LLM 产出完整 A→U 路径，或按需再拆成显式节点/边。
- **结构化输出**：`schemas.py` 里 6 个 Pydantic 模型，LLM 用 `with_structured_output` 生成，下游可校验、可对照金标准评测。
- **人机协同**：`interrupt()` 在两处暂停——红线复核、报告终审。`main.run` 用 `Command(resume=...)` 恢复。

## 安装与运行

```bash
cd langgraph_diagnosis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 ANTHROPIC_API_KEY；POSTGRES_URL 可选（多轮记忆持久化）
```

运行一例（交互式，遇红线/终审会暂停等你输入）：

```bash
python main.py REAL-006
```

一次性结构化输出（自动 approve，跳过人工，便于批跑/评测）：

```bash
python main.py REAL-006 --json
```

报告写盘 + 决策链图一并生成（markdown 报告 + mermaid `.mmd` + 渲染 `.svg`/`.png`，需 `mmdc`）：

```bash
python main.py REAL-006 -o reports/REAL-006.md
```

## Web 前端（React + Vite）

把流水线包装成可交互网页：流式决策链 A→U 点亮、红线复核 / 报告终审弹窗、随时停止。

- **决策链可视化**：A→U 全图按类别配色（起点 / 决策 / 早期 / 晚期 / 支持），只高亮当前阶段路径、未走过灰显。
- **流式反馈**：节点逐个点亮、追踪逐行追加、报告分节浮现，顶部实时状态胶囊（运行转圈 / 等待复核发光）。
- **引用与溯源**：报告中的引用分两类、均可点击回看原文——
  - 指南引用（青色徽章 `[章节 · P页码]`）→ 打开对应指南片段
  - 病历引用（蓝色徽章 `[病历·字段]`）→ 打开原始病历证据

**开发**（前端热更新，`/api` 代理到 FastAPI）：

```bash
cd langgraph_diagnosis/web && npm install && npm run dev   # 终端 1，http://localhost:5173
cd langgraph_diagnosis && .venv/bin/python server.py        # 终端 2，http://127.0.0.1:8000
```

**生产**（构建后由 FastAPI 直接托管）：

```bash
cd langgraph_diagnosis/web && npm run build
cd .. && .venv/bin/python server.py   # http://127.0.0.1:8000
```

后端端点：`GET /api/cases`、`GET /api/stream/{tid}?case_id=`（SSE 流式）、`POST /api/resume/{tid}`、`POST /api/stop/{tid}`。

> 已知边界：「停止」在节点边界生效（LLM 调用进行中会等当前节点结束）；客户端中途断连时，若正阻塞在复核等待，服务端线程会挂着（单用户可接受，多用户前需加断开检测/超时）。

## 关键设计取舍

1. **确定性 vs LLM 的分工**：JSON 解析、字段抽取、TNM 线索是确定性代码（可单测）；分子分型、分期判断、红线触发、A→U 走链、报告是 LLM（`temperature=0` + 结构化输出）。
2. **RAG 降级**：`GuideRetriever` 用本地多语言向量 `BAAI/bge-m3`（经 ModelScope/HF 下载，支持中英跨语言命中英文指南）；未装 embedding 依赖时自动退回 `BM25Retriever`（关键词，无需 embedding），保证可立即跑通。
3. **成本控制**：不把各指南全文（数百 KB）全塞进 prompt，只喂检索到的 top-k 章节；也不把 880KB JSON 全塞，只喂 `extract_features` 抽出的证据文本。
4. **评测入口**：`--json` 输出与 `Data_Cleaning/doc/系统输入/7例真实病例-患者基本情况与诊疗金标准.md` 可直接做字段级对照。
5. **可溯源的引用**：检索指南时携带章节+页码；报告里的指南证据（治疗评价/后续建议/分子分型）与病历证据（主要诊断/分期）都标注来源，前端可点击回看原文。

## 文件

| 文件 | 职责 |
|---|---|
| `config.py` | 路径、病例映射、模型/检索配置（环境变量覆盖） |
| `schemas.py` | Pydantic：结构化输出模型 + 图状态 |
| `extractor.py` | 确定性字段抽取（字段映射） |
| `guide_rag.py` | LlamaIndex 指南检索（向量/BM25 降级，附章节+页码来源） |
| `nodes.py` | 图节点：确定性节点 + LLM 判断节点 + interrupt 节点 |
| `graph.py` | StateGraph 组装 + 条件边 + HITL |
| `render.py` | 结构化结果 → markdown 报告 + 高亮决策链 mermaid |
| `main.py` | CLI 入口（交互 / JSON / markdown+图 输出 / resume） |
| `server.py` | FastAPI + SSE 后端：流式跑图、interrupt 转人工复核、serve 前端 |
| `web/` | React + Vite 前端（决策链可视化 + 流式报告 + 复核弹窗） |

## 已知边界（相对 skill 尚未覆盖）

- **跨指南对比范围**：`compare_guides` 仅并列 CSCO vs CACA；NCCN/SITC 作为检索证据源进入报告引用，不参与结构化对比/冲突检测（见根 README「已知边界」）。
- **多癌种**：当前聚焦 HER2+ 乳腺癌，决策链节点与红线清单均按乳腺癌定制。
