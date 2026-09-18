"""指南 RAG（LlamaIndex）：多指南，每份指南独立建索引，检索结果带指南身份。

默认 GUIDE_RETRIEVER=auto：
- 装了 llama-index-embeddings-huggingface → 本地中文向量（BAAI/bge-m3）语义检索
- 没装 → BM25Retriever（关键词检索，无需 embedding，可立即跑通）
"""
from __future__ import annotations

import re
from pathlib import Path

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.schema import Document

import config


def _build_nodes(guide_path: Path) -> list:
    text = guide_path.read_text(encoding="utf-8")
    parser = MarkdownNodeParser()
    return parser.get_nodes_from_documents([Document(text=text)])


def _extract_page(text: str) -> str | None:
    m = re.search(r"Page\s+(\d+)", text)
    return m.group(1) if m else None


def _extract_section(meta: dict, text: str) -> str | None:
    """取指南章节：优先 header_path 的顶层章节，退化到正文首个 # 标题。"""
    parts = [p for p in (meta.get("header_path") or "/").split("/") if p.strip()]
    if parts:
        return parts[0]
    m = re.search(r"^#\s+(.+)", text, re.MULTILINE)
    return m.group(1).strip() if m else None


class GuideRetriever:
    def __init__(self, profiles: list | None = None, top_k: int | None = None):
        self.profiles = profiles or config.GUIDE_PROFILES
        self.top_k = top_k or config.GUIDE_TOP_K
        self._mode = self._resolve_mode()
        self._retrievers: dict[str, object] = {}
        self._build()

    def _resolve_mode(self) -> str:
        mode = config.GUIDE_RETRIEVER
        if mode != "auto":
            return mode
        # auto：优先本地中文向量；装不了则退回 BM25
        try:
            import llama_index.embeddings.huggingface  # noqa: F401
            return "vector"
        except ImportError:
            return "bm25"

    def _resolve_model_path(self) -> str:
        """优先用 ModelScope 本地缓存（国内可下大文件），失败则退回 HF 模型名。"""
        try:
            from modelscope import snapshot_download
            return snapshot_download(config.EMBEDDING_MODEL)
        except Exception:
            return config.EMBEDDING_MODEL

    def _build(self) -> None:
        for p in self.profiles:
            nodes = _build_nodes(p.path)
            self._retrievers[p.name] = self._build_retriever(nodes)

    def _build_retriever(self, nodes: list):
        if self._mode == "vector":
            try:
                from llama_index.embeddings.huggingface import HuggingFaceEmbedding
                Settings.embed_model = HuggingFaceEmbedding(model_name=self._resolve_model_path())
                index = VectorStoreIndex(nodes)
                return index.as_retriever(similarity_top_k=self.top_k)
            except Exception as e:  # 模型加载失败（网络受限）等 → 退回 BM25
                print(f"[RAG] 向量模型加载失败，退回 BM25：{e}")
                self._mode = "bm25"
        return BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=self.top_k)

    @property
    def mode(self) -> str:
        return self._mode

    def retrieve(self, query: str) -> list[str]:
        """返回各指南 top-k 片段文本，供判断节点使用。"""
        return [r["text"] for r in self.retrieve_with_sources(query)]

    def retrieve_with_sources(self, query: str) -> list[dict]:
        """返回各指南 top-k 片段及其来源（指南 + 章节 + 页码），供报告引用。"""
        out = []
        for name, retriever in self._retrievers.items():
            for n in retriever.retrieve(query):
                text = n.get_content()
                out.append({
                    "guide": name,
                    "text": text,
                    "section": _extract_section(n.metadata, text),
                    "page": _extract_page(text),
                })
        return out


def build_query(features) -> str:
    """按病例特征构造检索 query（指南无关：分子分型 + 分期 + 转移部位 + 治疗阶段）。"""
    parts = ["乳腺癌 分子分型 HER2 ER PR Ki-67 判读"]
    d = ";".join(features.diagnoses or [])
    if d:
        parts.append(f"诊断：{d}")
    if features.pathology_text:
        parts.append(f"病理：{features.pathology_text[:200]}")
    # 转移部位决定要检索骨转移/脑转移章节
    blob = (features.tnm_text + features.imaging_text + features.narrative_text).lower()
    if any(k in blob for k in ("脑转移", "脑继发", "小脑", "脑膜")):
        parts.append("脑转移")
    if any(k in blob for k in ("骨转移", "骨继发", "肋骨", "椎体")):
        parts.append("骨转移")
    if "M1" in features.tnm_text or "Ⅳ期" in features.tnm_text or "IV期" in features.tnm_text:
        parts.append("晚期解救治疗")
    else:
        parts.append("新辅助治疗 辅助治疗")
    return " ".join(parts)
