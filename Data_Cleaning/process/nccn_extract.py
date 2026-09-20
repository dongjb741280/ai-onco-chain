#!/usr/bin/env python3
"""Extract the NCCN breast cancer guideline PDF (English) to Markdown.

NCCN 是英文、文本型 PDF（算法流程图 + 叙述）。逐页抽文本，去掉每页重复的
页眉/页脚样板，按页标签（BINV-N / MS-N）建标题分块，并加
`<!-- ===== Page NNN ===== -->` 页标记（与 guide_csco.md 一致，供引用溯源 + 分页 chunk）。
"""
import re
import fitz

SRC = "Data_Cleaning/doc/nccn/（2026.V6）NCCN临床实践指南：乳腺癌.pdf"
OUT = "Data_Cleaning/process/output/guide_nccn.md"

# 每页重复的页眉/页脚样板，整行丢弃
_BOILERPLATE = (
    "National Comprehensive Cancer Network",
    "NCCN Guidelines Version",
    "NCCN Clinical Practice Guidelines",
    "All rights reserved",
    "may not be reproduced",
    "NCCN Guidelines Index",
    "Table of Contents",
    "Note: All recommendations are category 2A unless otherwise indicated.",
    "Version 6.2026",
    "Continued",
)

_LABEL_RE = re.compile(r"\s*(?:BINV|MS|NON)-[A-Z0-9]+\s*")


def clean_lines(text):
    out = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if any(b in s for b in _BOILERPLATE):
            continue
        out.append(s)
    return out


def main():
    doc = fitz.open(SRC)
    out = []
    for pno in range(doc.page_count):
        lines = clean_lines(doc[pno].get_text())
        if not lines:
            continue
        label = None
        for ln in lines:
            if _LABEL_RE.fullmatch(ln) and len(ln) <= 12:
                label = ln
                break
        out.append(f"# {label or 'NCCN'}\n")
        out.append(f"<!-- ===== Page {pno + 1:03d} ===== -->\n")
        out.append("\n".join(lines))
        out.append("")
    md = "\n".join(out)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {OUT}: {len(md)} chars, {doc.page_count} pages")


if __name__ == "__main__":
    main()
