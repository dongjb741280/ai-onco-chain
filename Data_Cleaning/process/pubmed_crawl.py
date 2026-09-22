#!/usr/bin/env python3
"""Crawl PubMed literature (English abstracts) to Markdown for the retrieval KB.

Uses NCBI E-utilities (no API key, polite single search + single fetch). Query
defaults to breast cancer open-access literature (PMC OA subset, so --fulltext
works on nearly every record); override with --query.
Records are written as `## <title>` sections with a
`<!-- ===== PMID NNN ===== -->` marker (same citation/chunking convention as the
guide_*.md files) so guide_rag.py can index them alongside the guidelines.
"""
import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OUT_DEFAULT = "Data_Cleaning/process/output/literature_breast_cancer.md"


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-onco-chain/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def search(query, retmax, mindate, maxdate):
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "sort": "date",
    }
    if mindate:
        params["mindate"] = mindate
    if maxdate:
        params["maxdate"] = maxdate
    url = BASE + "esearch.fcgi?" + urllib.parse.urlencode(params)
    data = json.loads(http_get(url))
    return data["esearchresult"].get("idlist", [])


def fetch(pmids):
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    url = BASE + "efetch.fcgi?" + urllib.parse.urlencode(params)
    return ET.fromstring(http_get(url))


def first_text(elem, path, default=""):
    e = elem.find(path)
    if e is None or e.text is None:
        return default
    return e.text.strip()


def record_from_article(art):
    pmid = first_text(art, "MedlineCitation/PMID")
    title = first_text(art, "MedlineCitation/Article/ArticleTitle")

    year = first_text(art, "MedlineCitation/Article/Journal/JournalIssue/PubDate/Year")
    if not year:
        year = first_text(art, "MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate")
    if not year:
        year = first_text(art, "MedlineCitation/Article/ArticleDate/Year")

    journal = first_text(art, "MedlineCitation/Article/Journal/Title")

    doi = ""
    pmcid = ""
    for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
        idtype = aid.get("IdType")
        if idtype == "doi":
            doi = (aid.text or "").strip()
        elif idtype == "pmc":
            pmcid = (aid.text or "").strip()

    authors = []
    for a in art.findall("MedlineCitation/Article/AuthorList/Author"):
        coll = first_text(a, "CollectiveName")
        if coll:
            authors.append(coll)
            continue
        last = first_text(a, "LastName")
        fore = first_text(a, "ForeName") or first_text(a, "Initials")
        if last:
            authors.append(f"{last} {fore}".strip() or last)

    types = [
        t.text.strip()
        for t in art.findall("MedlineCitation/Article/PublicationTypeList/PublicationType")
        if t.text
    ]

    abstract = []
    for ab in art.findall("MedlineCitation/Article/Abstract/AbstractText"):
        label = ab.get("Label")
        text = "".join(ab.itertext()).strip()
        if not text:
            continue
        abstract.append((label, text))

    return {
        "pmid": pmid,
        "title": title,
        "year": year,
        "journal": journal,
        "doi": doi,
        "pmcid": pmcid,
        "authors": authors,
        "types": types,
        "abstract": abstract,
    }


def _collect_sec(sec, sections):
    title = " ".join((sec.find("title") or ET.Element("title")).itertext()).strip()
    paras = [" ".join(p.itertext()).strip() for p in sec.findall("p")]
    paras = [p for p in paras if p]
    if title or paras:
        sections.append((title, paras))
    for sub in sec.findall("sec"):
        _collect_sec(sub, sections)


def fulltext_from_pmc(pmcid):
    """Fetch PMC OA full-text XML and flatten body sections to (title, [paras])."""
    params = {"db": "pmc", "id": pmcid, "retmode": "xml"}
    url = BASE + "efetch.fcgi?" + urllib.parse.urlencode(params)
    try:
        root = ET.fromstring(http_get(url))
    except Exception:
        return None
    body = root.find(".//body")
    if body is None:
        return None
    sections = []
    for child in body:
        if child.tag == "sec":
            _collect_sec(child, sections)
        elif child.tag == "p":
            t = " ".join(child.itertext()).strip()
            if t:
                sections.append(("", [t]))
    return sections or None


def render(rec):
    out = [f"## {rec['title']}", ""]
    meta = f"**PMID**: {rec['pmid']}"
    if rec["journal"]:
        meta += f" · **Journal**: {rec['journal']}"
    if rec["year"]:
        meta += f" · **Year**: {rec['year']}"
    if rec["doi"]:
        meta += f" · **DOI**: {rec['doi']}"
    if rec["pmcid"]:
        meta += f" · **PMCID**: {rec['pmcid']}"
    out.append(meta)
    out.append("")
    if rec["authors"]:
        out.append("**Authors**: " + ", ".join(rec["authors"]))
        out.append("")
    if rec["types"]:
        out.append("**Types**: " + ", ".join(rec["types"]))
        out.append("")
    if rec["abstract"]:
        for label, text in rec["abstract"]:
            prefix = f"**{label}**: " if label else ""
            out.append(prefix + text)
            out.append("")
    else:
        out.append("[No abstract]")
        out.append("")
    for title, paras in rec.get("fulltext") or []:
        if title:
            out.append(f"**{title}**")
            out.append("")
        for p in paras:
            out.append(p)
            out.append("")
    return out


def main():
    ap = argparse.ArgumentParser(description="Crawl PubMed abstracts (and optional PMC full text) to Markdown")
    ap.add_argument("--query", default='breast cancer AND "pubmed pmc open access"[sb]')
    ap.add_argument("--retmax", type=int, default=100)
    ap.add_argument("--mindate", default="2023/01/01")
    ap.add_argument("--maxdate", default="")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--fulltext", action="store_true", help="also fetch PMC open-access full text")
    args = ap.parse_args()

    pmids = search(args.query, args.retmax, args.mindate, args.maxdate)
    if not pmids:
        print("no results for query:", args.query)
        return

    time.sleep(0.5)
    root = fetch(pmids)
    records = [record_from_article(a) for a in root.findall("PubmedArticle")]

    if args.fulltext:
        fetched = 0
        for rec in records:
            if not rec["pmcid"]:
                continue
            time.sleep(0.35)
            ft = fulltext_from_pmc(rec["pmcid"])
            if ft:
                rec["fulltext"] = ft
                fetched += 1
        print(f"fulltext fetched: {fetched}/{sum(1 for r in records if r['pmcid'])} with PMCID")

    lines = [
        f"# {args.query} (PubMed)",
        "",
        f"> query: `{args.query}` · {len(records)} records · sort by date"
        + (f" · since {args.mindate}" if args.mindate else "")
        + (f" · until {args.maxdate}" if args.maxdate else ""),
        "",
    ]
    for rec in records:
        if not rec["title"]:
            continue
        lines.append(f"<!-- ===== PMID {rec['pmid']} ===== -->")
        lines.extend(render(rec))

    md = "\n".join(lines).strip() + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    with_abs = sum(1 for r in records if r["abstract"])
    print(f"wrote {args.out}: {len(records)} records ({with_abs} with abstract)")


if __name__ == "__main__":
    main()
