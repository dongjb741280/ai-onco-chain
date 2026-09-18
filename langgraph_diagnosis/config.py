"""路径、病例映射、模型配置。所有可覆盖项走环境变量（见 .env.example）。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 按 config.py 自身位置定位 .env，避免依赖运行时的 CWD
load_dotenv(Path(__file__).resolve().parent / ".env")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "Data_Cleaning" / "process" / "output"
PATIENT_DIR = REPO_ROOT / "Data_Cleaning" / "doc" / "系统输入"
GOLD_STANDARD_PATH = PATIENT_DIR / "7例真实病例-患者基本情况与诊疗金标准.md"


@dataclass(frozen=True)
class GuidelineProfile:
    """一份指南的检索/引用配置（多指南可插拔层，见 .scratch/multi-guide/spec.md）。"""
    name: str              # 指南标识，如 "CSCO" / "CACA"
    path: Path             # 该指南的 markdown
    citation_prefix: str   # 引用显示名，如 "CSCO" / "CACA"


# 参与检索与报告的指南（顺序 = 报告引用的展示顺序）
GUIDE_PROFILES: list[GuidelineProfile] = [
    GuidelineProfile(name="CSCO", path=OUTPUT_DIR / "guide_csco.md", citation_prefix="CSCO"),
    GuidelineProfile(name="CACA", path=OUTPUT_DIR / "guide_caca.md", citation_prefix="CACA"),
]

# 病例编号 → 文件名（与 skill 第一步的映射表一致）
CASES: dict[str, str] = {
    "REAL-001": "REAL-001-严格标准版.json",
    "REAL-002": "REAL-002-严格标准版.json",
    "REAL-003": "REAL-003-大悟县首程-脱敏映射.json",
    "REAL-004": "REAL-004-首程2-脱敏映射.json",
    "REAL-005": "REAL-005-首程3-脱敏映射.json",
    "REAL-006": "REAL-006-深圳南山入院-严格标准版.json",
    "REAL-007": "REAL-007-深圳南山入院-严格标准版.json",
}

# LLM
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")  # None = 默认 Anthropic 端点

# RAG
GUIDE_RETRIEVER = os.getenv("GUIDE_RETRIEVER", "auto")  # auto | vector | bm25
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
GUIDE_TOP_K = int(os.getenv("GUIDE_TOP_K", "6"))

# 图状态持久化（多轮记忆）：未设置 POSTGRES_URL 时退回内存 checkpointer
POSTGRES_URL = os.getenv("POSTGRES_URL")  # 如 postgresql://user:pass@localhost:5432/db


def resolve_patient_path(case: str | Path) -> Path:
    """支持 REAL-XXX 编号或直接文件路径。"""
    p = Path(case)
    if p.exists():
        return p
    if case in CASES:
        return PATIENT_DIR / CASES[case]
    raise FileNotFoundError(f"未找到病例：{case}")
