#!/usr/bin/env python3
"""Extract the SITC immunotherapy-for-breast-cancer guideline PDF (English) to Markdown.

SITC 是英文、文本型叙述指南（34 页）。逐页抽文本，去掉页眉/页脚样板，
按章节标题（ABSTRACT / Panel recommendations / CONCLUSION …）建标题分块，
加 <!-- ===== Page NNN ===== --> 页标记（与其它 guide_*.md 一致，供引用溯源 + 分页 chunk）。
"""
import re
import fitz

SRC = "Data_Cleaning/doc/sitc/e002597.full.pdf"
OUT = "Data_Cleaning/process/output/guide_sitc.md"

_BOILERPLATE = (
    "Emens LA, et al.",
    "Open access",
    "doi:10.1136/jitc-2021-002597",
)

_HEADING_RE = re.compile(
    r"^(?:ABSTRACT|INTRODUCTION|GUIDELINE DEVELOPMENT METHODS|Recommendation development"
    r"|Panel recommendations|CONCLUSION|REFERENCES|ACKNOWLEDGEMENTS)$"
)


def clean_lines(text):
    out = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if any(b in s for b in _BOILERPLATE):
            continue
        if s.isdigit():  # 页脚页码
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
        heading = None
        for ln in lines:
            if _HEADING_RE.match(ln):
                heading = ln
                break
        out.append(f"# {heading or 'SITC'}\n")
        out.append(f"<!-- ===== Page {pno + 1:03d} ===== -->\n")
        out.append("\n".join(lines))
        out.append("")
    md = "\n".join(out)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {OUT}: {len(md)} chars, {doc.page_count} pages")


if __name__ == "__main__":
    main()
