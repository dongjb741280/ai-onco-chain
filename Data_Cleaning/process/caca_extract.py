#!/usr/bin/env python3
"""Extract the two-column breast-cancer guideline PDF to Markdown.

Body text is collected into a single stream ordered by (page, column, y) so
paragraphs flow correctly across column and page boundaries. Headings are
recovered from the section-numbering scheme (1 / 1.1 / 1.1.1 ...); the title
page front matter (title / authors / abstract) gets a dedicated pass.
"""
import re
import fitz

SRC = "Data_Cleaning/doc/caca/中国抗癌协会乳腺癌诊治指南与规范（2026 年版）.pdf"
OUT = "Data_Cleaning/process/output/中国抗癌协会乳腺癌诊治指南与规范（2026 年版）.md"

COL_SPLIT = 310.0   # x separating left / right column
HEADER_Y = 58.0     # running header + page number live above this y
LEFT_MARGIN = 65.0
RIGHT_MARGIN = 318.0
INDENT_TOL = 15.0   # first-line indent is ~22pt; flag x0 beyond margin+tol

heading_re = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
num_only_re = re.compile(r"^(\d+(?:\.\d+)*)$")
bullet_re = re.compile(r"^[⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿⒀⒁⒂⒃⒄⒅⒆⒇]")
dose_re = re.compile(r"^\d[\d\s]*\s?(?:mg|mL|ml|cm|mm|μm|μg|kg|g|kU|U|IU|min|h|d|mmol|μmol)\b")

OPEN_PARENS = "（("
CLOSE_PARENS = "）)"


def line_text(line):
    return "".join(s["text"] for s in line["spans"]).strip()


def get_lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            txt = line_text(l)
            if not txt:
                continue
            x0, y0, x1, y1 = l["bbox"]
            if y0 < HEADER_Y:
                continue
            sz = max((s["size"] for s in l["spans"]), default=0)
            out.append({"text": txt, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "sz": sz})
    return out


def valid_num(num):
    """Section numbers are dot-separated integers 1..99 (never '1.0'/'0.5')."""
    return all(1 <= int(p) <= 99 for p in num.split("."))


def heading_level(num):
    return num.count(".") + 1  # "1" -> 1, "1.1" -> 2, ...


def paren_unbalanced(s):
    return sum(s.count(c) for c in OPEN_PARENS) > sum(s.count(c) for c in CLOSE_PARENS)


def is_heading_line(t):
    return bool(heading_re.match(t) or num_only_re.match(t))


def title_ok(title):
    """Section titles begin with CJK or a digit (age ranges); reject dose/unit cells."""
    t = title.strip()
    if not t:
        return True
    c = t[0]
    if c.isascii() and c.isalpha():
        return False
    if dose_re.match(t):
        return False
    return True


def emit(lines, out):
    """Classify and group an ordered line stream into markdown."""
    i = 0
    para = []
    max_section = 0  # highest single-integer section seen; detects numbering restarts

    def flush():
        nonlocal para
        if para:
            text = "".join(para).strip()
            para = []
            if text:
                out.append(text)
                out.append("")

    while i < len(lines):
        txt = lines[i]["text"]
        m = heading_re.match(txt)
        mnum = num_only_re.match(txt)
        margin = RIGHT_MARGIN if lines[i]["x0"] >= COL_SPLIT else LEFT_MARGIN
        at_margin = lines[i]["x0"] <= margin + 3.0  # section headings sit at the column margin

        if m and valid_num(m.group(1)) and at_margin and title_ok(m.group(2)):
            flush()
            lvl = heading_level(m.group(1))
            num = m.group(1)
            if "." not in num:
                n = int(num)
                if n <= max_section:
                    lvl = 2  # numbering restarted: a numbered list/table title, not a top section
                else:
                    max_section = n
            h = "#" * (lvl + 1)
            title = m.group(2).strip()
            i += 1
            while i < len(lines) and paren_unbalanced(title):
                nxt = lines[i]["text"]
                if is_heading_line(nxt) or bullet_re.match(nxt):
                    break
                title += nxt
                i += 1
            out.append(f"{h} {m.group(1)} {title}")
            out.append("")
            continue

        if mnum and "." in mnum.group(1) and valid_num(mnum.group(1)) and at_margin:
            flush()
            h = "#" * (heading_level(mnum.group(1)) + 1)
            title_parts = []
            i += 1
            if i < len(lines):
                nxt = lines[i]
                if not (is_heading_line(nxt["text"]) or bullet_re.match(nxt["text"])):
                    title_parts.append(nxt["text"])
                    i += 1
            while i < len(lines) and paren_unbalanced("".join(title_parts)):
                nxt = lines[i]["text"]
                if is_heading_line(nxt) or bullet_re.match(nxt):
                    break
                title_parts.append(nxt)
                i += 1
            out.append(f"{h} {mnum.group(1)} {' '.join(title_parts).strip()}".rstrip())
            out.append("")
            continue

        # body line
        indented = lines[i]["x0"] > (RIGHT_MARGIN if lines[i]["x0"] >= COL_SPLIT else LEFT_MARGIN) + INDENT_TOL
        if bullet_re.match(txt) and indented:
            flush()
            out.append(f"- {txt}")
            i += 1
            continue
        if indented:
            flush()
            para.append(txt)
        else:
            para.append(txt)
        i += 1
    flush()


SKIP_MARKERS = ("《中国癌症杂志》", "CHINA ONCOLOGY", "·指南与共识·", "中图分类号", "DOI:")


def process_title_page(page, out):
    """Emit front matter (title/authors/abstract) and return the section-1 body lines."""
    lines = get_lines(page)
    # drop 8pt metadata sidebar and the top-right page number
    lines = [l for l in lines if l["sz"] >= 8.5]
    lines = [l for l in lines if not (l["sz"] == 9.0 and l["text"].strip().isdigit())]
    lines = [l for l in lines if not any(l["text"].startswith(m) for m in SKIP_MARKERS)]

    body_start = 740.0
    front = [l for l in lines if l["y0"] < body_start]
    body = [l for l in lines if l["y0"] >= body_start]

    title = "".join(l["text"] for l in front if l["sz"] >= 20).strip()
    if title:
        out.append(f"# {title}")
        out.append("")

    authors = [l["text"] for l in front if 11.5 <= l["sz"] <= 12.5 and l["x0"] < COL_SPLIT]
    if authors:
        out.append(" ".join(authors).strip())
        out.append("")

    left_front = sorted([l for l in front if l["x0"] < COL_SPLIT], key=lambda l: (l["y0"], l["x0"]))

    def emit_labeled(start_idx, marker):
        i = start_idx
        buf = []
        while i < len(left_front) and not left_front[i]["text"].startswith(marker):
            buf.append(left_front[i]["text"])
            i += 1
        return buf, i

    i = 0
    while i < len(left_front):
        t = left_front[i]["text"]
        if t.startswith("［摘要］"):
            buf, i = emit_labeled(i + 1, "［关键词］")
            out.append("## 摘要")
            out.append("")
            out.append(t[len("［摘要］"):] + "".join(buf).strip() if buf else t[len("［摘要］"):])
            out.append("")
            continue
        if t.startswith("［关键词］"):
            out.append(f"**关键词：** {t[len('［关键词］'):].strip()}")
            out.append("")
            i += 1
            continue
        if t.startswith("［Abstract］"):
            buf, i = emit_labeled(i + 1, "［Keywords］")
            out.append("## Abstract")
            out.append("")
            out.append(t[len("［Abstract］"):] + " ".join(buf).strip() if buf else t[len("［Abstract］"):])
            out.append("")
            continue
        if t.startswith("［Keywords］"):
            out.append(f"**Keywords:** {t[len('［Keywords］'):].strip()}")
            out.append("")
            i += 1
            continue
        i += 1

    return body


def main():
    doc = fitz.open(SRC)
    out = []

    body = process_title_page(doc[0], out)

    stream = []
    for l in body:
        col = 0 if l["x0"] < COL_SPLIT else 1
        stream.append((0, col, l["y0"], l["x0"], l))
    for pno in range(1, doc.page_count):
        for l in get_lines(doc[pno]):
            col = 0 if l["x0"] < COL_SPLIT else 1
            stream.append((pno, col, l["y0"], l["x0"], l))
    stream.sort(key=lambda x: x[:4])
    emit([x[4] for x in stream], out)

    md = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {OUT}: {len(md)} chars, {doc.page_count} pages")


if __name__ == "__main__":
    main()
