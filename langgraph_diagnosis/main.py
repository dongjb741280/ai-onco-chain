"""CLI 入口：跑一例输出格式化诊断报告（默认），或结构化 JSON。

用法：
  python main.py REAL-006                     # 输出格式化 markdown 诊断（默认自动通过红线/终审，不卡交互）
  python main.py REAL-006 --json              # 结构化 JSON 输出（供评测/流水线）
  python main.py REAL-006 --interactive       # 遇红线/终审时人工决策
  python main.py REAL-006 --thread t1         # 指定 thread_id，便于 resume
  python main.py REAL-006 -o reports/REAL-006.md   # 报告写 .md，并一并生成决策链 .mmd/.svg/.png（默认打印到 stdout）
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from langgraph.types import Command

import config
from graph import get_graph
from render import render_decision_chain_mmd, render_diagnosis


def run(case: str, thread_id: str, auto_approve: bool = False) -> dict:
    graph = get_graph()
    path = config.resolve_patient_path(case)
    cfg = {"configurable": {"thread_id": thread_id}}

    state = {"case_id": case, "patient_path": str(path)}
    result = graph.invoke(state, cfg)

    # 处理人机协同暂停点（interrupt）
    while result.get("__interrupt__"):
        inter = result["__interrupt__"][0]
        kind = inter.value.get("type")
        if kind == "red_line_review":
            print("\n[红线复核] 命中红线：")
            for r in inter.value.get("red_lines", []):
                print(f"  - {r.get('kind')}: {r.get('description')} → {r.get('action')}")
            if auto_approve:
                decision = {"decision": "proceed", "note": "auto-approve"}
            else:
                d = input("人工决策 [proceed/stop/revise]，默认 proceed：").strip() or "proceed"
                decision = {"decision": d}
        elif kind == "report_approval":
            if auto_approve:
                decision = {"decision": "approve"}
            else:
                d = input("报告终审 [approve/revise]，默认 approve：").strip() or "approve"
                decision = {"decision": d}
        else:
            decision = {"decision": "approve"}
        result = graph.invoke(Command(resume=decision), cfg)

    return result


def _dump(result: dict) -> str:
    out = {
        "case_id": result.get("case_id"),
        "subtype": result.get("subtype").model_dump() if result.get("subtype") else None,
        "staging": result.get("staging").model_dump() if result.get("staging") else None,
        "red_lines": [r.model_dump() for r in result.get("red_lines", [])],
        "chain_path": [s.model_dump() for s in result.get("chain_path", [])],
        "trace_summary": result.get("trace_summary").model_dump() if result.get("trace_summary") else None,
        "guide_comparison": [e.model_dump() for e in result.get("guide_comparison", [])],
        "report": result.get("report").model_dump() if result.get("report") else None,
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


def _write_diagram(result: dict, case: str, out: Path) -> None:
    """把决策链 mermaid 写到报告同目录，并尝试 mmdc 渲染 svg/png（可选）。"""
    mmd = render_decision_chain_mmd(result)
    slug = Path(case).stem or "case"
    mmd_path = out.parent / f"decision-chain-{slug}.mmd"
    mmd_path.write_text(mmd + "\n", encoding="utf-8")
    print(f"已写入 {mmd_path}")

    if shutil.which("mmdc"):
        for ext, extra in ((".svg", ["-b", "white"]), (".png", ["-b", "white", "-s", "2"])):
            target = out.parent / f"decision-chain-{slug}{ext}"
            subprocess.run(
                ["mmdc", "-i", str(mmd_path), "-o", str(target), *extra],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if target.exists():
                print(f"已渲染 {target}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", help="REAL-XXX 编号或 JSON 路径")
    ap.add_argument("--json", action="store_true", help="结构化 JSON 输出（供评测/流水线）")
    ap.add_argument("--interactive", action="store_true", help="遇红线/终审时人工决策（默认自动通过）")
    ap.add_argument("--thread", default=None, help="thread_id（用于 resume）")
    ap.add_argument("-o", "--output", default=None, help="写入文件（markdown 报告或 --json 的 JSON）；默认打印到 stdout")
    args = ap.parse_args()

    thread = args.thread or f"{args.case}-run"
    result = run(args.case, thread, auto_approve=not args.interactive)

    text = _dump(result) if args.json else render_diagnosis(result)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {out}")
        if not args.json:
            _write_diagram(result, args.case, out)
    else:
        print(text)


if __name__ == "__main__":
    main()
