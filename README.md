# ai-onco-chain

从 **CSCO + CACA + NCCN + SITC** 乳腺癌诊疗指南与脱敏病例构建的诊疗辅助流水线：把一份病历（`REAL-XXX` JSON）加上多份指南，自动产出**综合诊断报告**、**跨指南对比**、**A→U 决策链追踪**与高亮 **mermaid 图**，并对齐脱敏病例金标准做评测。当前范围聚焦 **HER2+ 乳腺癌**。

> 临床辅助工具，不替代主诊医师 / MDT 决策。

## 仓库结构

```text
.
├── langgraph_diagnosis/   # 主流水线：LangGraph 图编排 + 多指南 RAG + 结构化输出 + 人机协同
│   ├── structured_decisions.py  # 结构化决策层：CSCO 决策表解析 + CACA LLM 抽取 + 跨指南 diff/裁决
│   ├── server.py          # FastAPI + SSE 后端（流式诊断 + 人工复核）
│   └── web/               # React + Vite 前端
├── Data_Cleaning/         # 数据侧：指南 PDF → 抽取/OCR → 归一化 → guide_{csco,caca,nccn,sitc}.md；病例与金标准
│   ├── process/       # 指南抽取/OCR（csco/caca/nccn/sitc），产出 guide_*.md
│   └── doc/系统输入/       # 脱敏病例 JSON（REAL-* / BC-*）+ 诊疗金标准（git 不入库）
├── skill_diagnosis/       # skill 产出的决策链图（.mmd / .svg / .png / .excalidraw）
├── .claude/skills/
│   └── diagnosis-report/  # 同一诊疗场景的 prompt 版 skill（流水线的语义来源）
├── .scratch/hybrid-kb/    # issue 跟踪：混合型知识库（结构化决策层 + 图谱 + 融合检索）的 spec
├── .scratch/multi-guide/  # issue 跟踪：多指南融合（可插拔指南层 / 跨指南对比 / 冲突裁决）的 spec
├── docs/agents/           # 领域文档 / issue 跟踪 / triage 标签约定
└── CONTEXT.md             # 领域术语表（推荐决策 / 方案 / 药物 / 推荐等级 / 证据类别 …）
```

## Skill：diagnosis-report（prompt 版）

`.claude/skills/diagnosis-report/SKILL.md` 是同一诊疗场景的 prompt 版 skill，也是主流水线的语义来源。不依赖任何 Python 脚本：Claude 直接读病历 + CSCO 指南，一次抽取、两个输出——

1. **综合诊断报告**：主要诊断 / 分子分型 / TNM 分期 / 诊疗经过 / 治疗评价 / 后续建议 / 待核实
2. **决策链追踪 A→U**（回溯该病例走到了哪个节点、凭什么）+ 高亮 mermaid 图

输入三选一：`REAL-XXX` 编号、病历 JSON 路径、粘贴自由文本。触发语如「出一份诊断 / 根据病历和指南出诊断 / 走决策链 / 生成决策链图」。

产出的决策链图落在 `skill_diagnosis/`：`breast-cancer-treatment-decision-chain.*` 为总览，`decision-chain-REAL-001..007.*` 为各病例实例；`.mmd` 是 mermaid 源、`.svg`/`.png` 是渲染图、`.excalidraw` 是白板。

## 主流水线：langgraph_diagnosis

把 skill 里的诊疗场景重写为可批量、可评测、可生产化的 Python 流水线。skill 里 80% 的价值——领域红线与证据锚定的 prompt 规则——原样搬进 prompt，确定性抽取下沉为代码。提供 **CLI**（`main.py`）与 **Web 前端**（`server.py` + `web/`，React + Vite）两个入口。

### 图结构

```text
START → load_patient → extract_features → judge_subtype → judge_staging
      → retrieve_guide（分型/分期感知 query）→ check_red_lines
      → 〔条件边〕 命中红线 → human_review(interrupt) → trace_chain
                  无红线        → trace_chain
      → compare_guides → write_report → human_approve(interrupt) → END
```

- **确定性代码**：JSON 解析、字段抽取、TNM 线索（`extractor.py`），可单测。
- **LLM 结构化输出**：分子分型 / 分期 / 红线 / A→U 走链 / 报告（`schemas.py` 的 6 个 Pydantic 模型，`temperature=0`）。
- **RAG 降级**：`GuideRetriever` 用本地多语言向量 `BAAI/bge-m3`（中英跨语言，经 ModelScope/HF 下载，命中英文 NCCN/SITC）；未装 embedding 依赖则自动退回 BM25 关键词检索，无需 key 也能跑通。
- **人机协同**：红线复核、报告终审两处 `interrupt()` 暂停，`main.run` 用 `Command(resume=...)` 恢复。
- **多轮记忆**：`POSTGRES_URL` 配置时用 Postgres 持久化 checkpoint，否则退回内存。

### 安装与运行

```bash
cd langgraph_diagnosis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 ANTHROPIC_API_KEY；POSTGRES_URL 可选
```

冒烟测试（验证确定性层，不调 LLM）：

```bash
.venv/bin/python smoke_test.py
```

运行一例（默认自动通过红线/终审，不卡交互）：

```bash
python main.py REAL-006
```

结构化 JSON（供评测 / 流水线）：

```bash
python main.py REAL-006 --json
```

人工决策（遇红线/终审时暂停等你输入）：

```bash
python main.py REAL-006 --interactive
```

报告写盘 + 一并生成决策链 `.mmd` / `.svg` / `.png`（需 `mmdc`）：

```bash
python main.py REAL-006 -o reports/REAL-006.md
```

### Web 前端

交互式网页：流式决策链 A→U 点亮（类别配色、只高亮当前阶段路径）、红线复核 / 报告终审弹窗、随时停止，报告中的指南/病历证据带可点击引用（回看原文）。

```bash
# 生产（构建后由 FastAPI 托管）
cd langgraph_diagnosis/web && npm install && npm run build
cd .. && .venv/bin/python server.py          # http://127.0.0.1:8000

# 开发（前端热更新，/api 代理到 FastAPI）
cd langgraph_diagnosis/web && npm run dev    # http://localhost:5173
cd langgraph_diagnosis && .venv/bin/python server.py
```

### 文件

| 文件 | 职责 |
| --- | --- |
| `config.py` | 路径、病例映射、模型/检索配置（环境变量覆盖） |
| `schemas.py` | Pydantic：结构化输出模型 + 图状态 |
| `extractor.py` | 确定性字段抽取（权威字段 + 叙事兜底） |
| `guide_rag.py` | LlamaIndex 指南检索（多指南，向量 / BM25 降级） |
| `structured_decisions.py` | 结构化决策层：CSCO 决策表解析 + CACA LLM 抽取 + 规范等级归一化 + 跨指南 diff/裁决 |
| `nodes.py` | 图节点：确定性节点 + LLM 判断节点 + interrupt 节点 |
| `graph.py` | StateGraph 组装 + 条件边 + HITL |
| `render.py` | 结构化结果 → markdown 报告 + 高亮决策链 mermaid |
| `main.py` | CLI 入口（交互 / JSON / markdown+图 / resume） |
| `server.py` | FastAPI + SSE 后端：流式跑图、interrupt 转人工复核、serve 前端 |
| `web/` | React + Vite 前端（决策链可视化 + 流式报告 + 复核弹窗） |

## 数据侧：Data_Cleaning

把四份指南转成 `guide_{csco,caca,nccn,sitc}.md`：`guide_csco.md`（`2026CSCO乳腺癌诊疗指南.pdf`，258 页，决策表含 Ⅰ/Ⅱ/Ⅲ 推荐等级与 1A/2B 等证据类别，OCR + 归一化）、`guide_caca.md`（《中国抗癌协会乳腺癌诊治指南与规范（2026 年版）》，按章节叙述，无统一推荐等级）、`guide_nccn.md`（英文 NCCN，fitz 抽算法页）、`guide_sitc.md`（英文 SITC 免疫治疗，补充）。归一化规则见 `.scratch/hybrid-kb/issues/02-guide-normalization.md`。CSCO/CACA 的推荐决策结构化抽取 + 跨指南 diff/裁决见 `structured_decisions.py`（CACA 结果缓存 `caca_decisions.json`）。

病例与金标准位于 `Data_Cleaning/doc/系统输入/`（脱敏后仍不入库，见 `.gitignore`）：

- 病例 JSON：`REAL-001..007`（严格标准版 / 脱敏映射版）、`BC-001..020`
- 金标准：`7例真实病例-患者基本情况与诊疗金标准.md`（自由文本参照，供 `--json` 输出做字段级对照）

## 评测

`python main.py <case> --json` 的结构化输出可直接与 `Data_Cleaning/doc/系统输入/7例真实病例-患者基本情况与诊疗金标准.md` 做字段级对照。更完整的评测协议（端到端 LLM-as-judge + 检索层 recall/precision）见 `.scratch/hybrid-kb/issues/07-eval-protocol.md`。

## 术语

领域标准用词见 `CONTEXT.md`：推荐决策 / 方案 / 药物 / 推荐等级（Ⅰ/Ⅱ/Ⅲ）/ 证据类别（1A..3）/ 治疗阶段 / 人群 / 分层条件 / 指南来源 / 规范推荐强度 / 规范证据等级 / 金标准。命名与输出时请遵循该术语表，避免使用其明确规避的同义词。

## 已知边界

- 多指南（CSCO/CACA/NCCN/SITC）均接入检索与报告引用；但跨指南对比（`compare_guides`）只做 CSCO vs CACA，境外指南（NCCN/SITC）作为检索证据源、不参与结构化对比与 diff。
- 确定性冲突检测（`structured_decisions.diff`）为方案名精确匹配、CACA 人群标签不统一，覆盖有限（见 `.scratch/multi-guide/issues/03`）。
- 多癌种不在当前范围，聚焦 HER2+ 乳腺癌。
