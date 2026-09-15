"""FastAPI 后端：SSE 流式跑诊断流水线，interrupt 转人工复核。

用法：
  python server.py          # 默认 127.0.0.1:8000
  python server.py --port 9000

端点：
  GET  /                    前端页面（web/dist/index.html，需先 npm run build）
  GET  /api/cases           病例列表（来自 config.CASES）
  GET  /api/stream/{tid}    启动并流式跑一例（SSE，case_id 走 query）
  POST /api/resume/{tid}    恢复暂停（{"decision": "proceed"|"approve"|"stop"|"revise"}）
  POST /api/stop/{tid}      终止当前运行
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command

import config
from graph import get_graph

WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
app = FastAPI(title="ai-onco-chain 诊疗流水线")

# 托管 Vite 构建产物（index.html + /assets/*）；未构建时挂空目录，稍后构建即可
app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets", check_dir=False), name="assets")

# thread_id -> 会话状态（决策回传 + 停止标志）
_sessions: dict[str, dict] = {}
_LOCK = threading.Lock()


def _session(thread_id: str) -> dict:
    with _LOCK:
        return _sessions.setdefault(
            thread_id, {"event": threading.Event(), "decision": None, "stopped": False}
        )


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


# ---------- 序列化（只把下游需要的字段发给前端，丢弃大体量原始数据） ----------

def _serialize_node(name: str, update: dict) -> dict:
    if name == "load_patient":
        return {"patient": {"name": update.get("patient_name"), "case_id": update.get("case_id")}}
    if name == "extract_features":
        f = update.get("features")
        if not f:
            return {"features": {}, "record": {}}
        return {
            "features": {"gender": f.gender, "age": f.age, "diagnoses": f.diagnoses},
            "record": {
                "诊断": "、".join(f.diagnoses) if f.diagnoses else "",
                "病理": f.pathology_text,
                "TNM/分期": f.tnm_text,
                "治疗": f.treatment_text,
                "影像": f.imaging_text,
                "检验": f.labs_text,
                "叙事": f.narrative_text,
            },
        }
    if name == "retrieve_guide":
        return {"guide_sources": update.get("guide_sources", [])}
    if name == "judge_subtype":
        s = update.get("subtype")
        return {"subtype": s.model_dump() if s else None}
    if name == "judge_staging":
        s = update.get("staging")
        return {"staging": s.model_dump() if s else None}
    if name == "check_red_lines":
        return {"red_lines": [r.model_dump() for r in update.get("red_lines", [])]}
    if name == "trace_chain":
        return {
            "chain_path": [s.model_dump() for s in update.get("chain_path", [])],
            "trace_summary": update.get("trace_summary").model_dump() if update.get("trace_summary") else None,
        }
    if name == "write_report":
        r = update.get("report")
        return {"report": r.model_dump() if r else None}
    return {}


def _serialize_interrupt(payload: dict) -> dict:
    kind = payload.get("type")
    if kind == "red_line_review":
        return {"type": kind, "red_lines": payload.get("red_lines", [])}
    if kind == "report_approval":
        return {"type": kind}
    return {"type": kind or "unknown", "payload": payload}


# ---------- 运行流 ----------

def _run_stream(thread_id: str, case_id: str, patient_path: str):
    """同步生成器：跑图并逐事件 yield SSE 文本；命中 interrupt 时阻塞等 resume。"""
    graph = get_graph()
    cfg = {"configurable": {"thread_id": thread_id}}
    state = {"case_id": case_id, "patient_path": patient_path}
    session = _session(thread_id)

    yield _sse("status", {"value": "running"})

    inp = state
    while True:
        interrupted = None
        try:
            for chunk in graph.stream(inp, cfg, stream_mode="updates"):
                if session["stopped"]:
                    yield _sse("status", {"value": "stopped"})
                    return
                for name, update in chunk.items():
                    if name == "__interrupt__":
                        interrupted = update[0].value
                        yield _sse("interrupt", _serialize_interrupt(interrupted))
                    else:
                        yield _sse("node", {"name": name, **_serialize_node(name, update)})
        except Exception as e:  # 节点内异常（API/网络等）
            yield _sse("run_error", {"message": str(e)})
            return

        if interrupted is None:
            break

        yield _sse("status", {"value": "paused"})
        decision = _wait_resume(session, thread_id)
        d = decision.get("decision") if isinstance(decision, dict) else None
        if d in ("stop", "revise"):
            yield _sse("status", {"value": "stopped" if d == "stop" else "revised"})
            return
        yield _sse("status", {"value": "running"})
        inp = Command(resume=decision)

    yield _sse("status", {"value": "done"})


def _wait_resume(session: dict, thread_id: str) -> dict | None:
    session["event"].wait()
    if session["stopped"]:
        return {"decision": "stop"}
    decision = session["decision"]
    session["decision"] = None
    session["event"].clear()
    return decision


# ---------- 端点 ----------

@app.get("/")
def index():
    index_file = WEB_DIST / "index.html"
    if not index_file.exists():
        return {"hint": "前端未构建，运行 cd web && npm install && npm run build"}
    return FileResponse(index_file)


@app.get("/api/cases")
def cases():
    return [{"id": k, "label": v} for k, v in config.CASES.items()]


@app.get("/api/stream/{thread_id}")
def stream(thread_id: str, case_id: str):
    try:
        path = config.resolve_patient_path(case_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    _session(thread_id)

    def gen():
        yield from _run_stream(thread_id, case_id, str(path))

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/resume/{thread_id}")
def resume(thread_id: str, body: dict = Body(...)):
    session = _sessions.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="no such run")
    session["decision"] = body
    session["event"].set()
    return {"ok": True}


@app.post("/api/stop/{thread_id}")
def stop(thread_id: str):
    session = _sessions.get(thread_id)
    if session:
        session["stopped"] = True
        session["event"].set()
    return {"ok": True}


if __name__ == "__main__":
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    print(f"启动诊疗流水线服务：http://{args.host}:{args.port}")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)
