"""Orbit — the NBody Labs autonomous account AI co-pilot (FastAPI).

Surfaces the product's documented behaviours:
  * account-aware answers, diagnostics, dashboard navigation, generative UI
  * write proposals that require an explicit human approval before executing
  * undo, conversation history, support cases, feedback signals, eval stats
  * access & permissions: Full / Read only / Custom, token rotation, write lock
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel


import cf
import do_store
import gateway
import permissions
import runtime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LLM_STATE = {"ready": False}
SESSIONS: dict[str, "Session"] = {}
SESSIONS_LOCK = threading.Lock()
_BUSY: set[str] = set()


class Session:
    def __init__(self, sid: str):
        self.sid = sid
        self.q: queue.Queue = queue.Queue()

    def emit(self, kind: str, data: dict):
        self.q.put({"type": kind, "data": data})


def _janitor():
    while True:
        time.sleep(60)
        with SESSIONS_LOCK:
            for sid in [s for s in SESSIONS if s not in _BUSY]:
                SESSIONS.pop(sid, None)


def _llm_poller():
    import wait_for_llm
    while True:
        try:
            LLM_STATE["ready"] = wait_for_llm.probe_ready()
        except Exception:
            LLM_STATE["ready"] = False
        time.sleep(10)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # stands in for the dashboard granting access when the assistant is opened
    try:
        permissions.load_catalogue()
        permissions.rotate_token()
    except Exception as exc:  # platform API may still be booting
        print(f"[orbit] initial token grant deferred: {exc}", flush=True)
    threading.Thread(target=_janitor, daemon=True).start()
    threading.Thread(target=_llm_poller, daemon=True).start()
    yield


app = FastAPI(title="Orbit Console", lifespan=lifespan)
templates = Jinja2Templates(directory=f"{BASE_DIR}/templates")


class NoCacheStatic(StaticFiles):
    """Static assets are rebuilt constantly during development; a cached
    app.js silently pins the browser to an old build, so never let one stick."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        return resp


app.mount("/static", NoCacheStatic(directory=f"{BASE_DIR}/static"), name="static")


class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    instruction_hierarchy: bool = True


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html",
                                      {"model": gateway.model_name()})


@app.get("/api/status")
def status():
    return {
        "ok": True,
        "model": gateway.model_name(),
        "model_ready": LLM_STATE["ready"],
        "cf_api": cf.health(),
        "write_available": permissions.write_available(),
    }


# ── chat ───────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(payload: ChatIn):
    cid = payload.conversation_id or do_store.new_conversation(payload.message[:60])
    sid = uuid.uuid4().hex
    sess = Session(sid)
    with SESSIONS_LOCK:
        SESSIONS[sid] = sess
        _BUSY.add(sid)

    def worker():
        try:
            agent = runtime.NBodyAgent(cid, sess.emit,
                              instruction_hierarchy=payload.instruction_hierarchy)
            agent.respond(payload.message)
        except Exception as exc:
            sess.emit("error", {"message": f"agent error: {exc}"})
        finally:
            with SESSIONS_LOCK:
                _BUSY.discard(sid)
            sess.emit("end", {"conversation_id": cid})

    threading.Thread(target=worker, daemon=True).start()
    return {"conversation_id": cid, "session": sid}


@app.get("/api/stream")
def stream(session: str):
    sess = SESSIONS.get(session)
    if sess is None:
        payload = {"type": "error", "data": {"message": "unknown session"}}
        return StreamingResponse(iter([f"data: {json.dumps(payload)}\n\n"]),
                                 media_type="text/event-stream")

    def gen():
        while True:
            try:
                evt = sess.q.get(timeout=15)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(evt)}\n\n"
            if evt["type"] in ("done", "end", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

# ── approval gate ──────────────────────────────────────────────────────

@app.get("/api/proposals")
def list_proposals(conversation_id: str | None = None):
    return do_store.list_proposals(conversation_id)


@app.post("/api/proposals/{proposal_id}/approve")
def approve(proposal_id: str):
    """Execute a proposed write — this is the ONLY path that mutates the account."""
    prop = do_store.get_proposal(proposal_id)
    if prop is None:
        return JSONResponse({"error": "proposal not found"}, status_code=404)
    if prop["status"] != "pending":
        return JSONResponse({"error": f"proposal is already {prop['status']}"},
                            status_code=409)
    if not permissions.write_available():
        return JSONResponse(
            {"error": "Write access has been disabled for your account by an "
                      "administrator."}, status_code=403)

    spec = runtime.mcp.ALL_TOOLS[prop["tool"]]
    args = dict(prop["args"])
    try:
        result = spec["fn"](**args)
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        do_store.decide(proposal_id, "failed", {"error": str(detail)})
        gateway.record_tool(prop["tool"], "failed")
        return JSONResponse({"error": str(detail)}, status_code=400)

    if prop["tool"] == "create_dns_record" and isinstance(result, dict):
        created_id = result.get("id") or (result.get("record") or {}).get("id")
        if created_id:
            args["_created_id"] = created_id

    updated = do_store.decide(proposal_id, "executed", {"result": result})
    gateway.record_tool(prop["tool"], "ok")
    do_store.record_change(prop["conversation_id"], proposal_id, prop["tool"], args,
                           prop["before_state"], prop["summary"])
    return {"proposal": updated, "result": result}


@app.post("/api/proposals/{proposal_id}/reject")
def reject(proposal_id: str):
    prop = do_store.get_proposal(proposal_id)
    if prop is None:
        return JSONResponse({"error": "proposal not found"}, status_code=404)
    updated = do_store.decide(proposal_id, "rejected", {})
    return {"proposal": updated}


@app.get("/api/changes")
def changes(conversation_id: str | None = None):
    return do_store.list_changes(conversation_id)


@app.post("/api/changes/{change_id}/undo")
def undo(change_id: str):
    """Undo is itself a proposal — never an automatic reversal."""
    rows = [c for c in do_store.list_changes() if c["id"] == change_id]
    if not rows:
        return JSONResponse({"error": "change not found"}, status_code=404)
    change = rows[0]
    class _Holder(runtime.NBodyAgent):
        def __init__(self):  # noqa: D107 - light shim
            self.conversation_id = change["conversation_id"]
    holder = _Holder()
    tool, undo_args = holder._undo_proposal(change)
    if tool is None:
        err = undo_args.get("error", "Cannot undo this change") if isinstance(undo_args, dict) else str(undo_args)
        return JSONResponse({"error": err}, status_code=400)
    prop = do_store.propose(
        change["conversation_id"], tool, undo_args,
        summary=f"Undo: {runtime._summarise(tool, undo_args)}",
        rationale=f"Undo of change {change_id}.",
        before_state=runtime._before_state(tool, undo_args),
    )
    return {"proposal": prop}


# ── history, feedback, evals ───────────────────────────────────────────

@app.get("/api/conversations")
def conversations():
    return do_store.list_conversations()


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str):
    return {"id": conversation_id,
            "messages": do_store.get_messages(conversation_id),
            "proposals": do_store.list_proposals(conversation_id)}


class FeedbackIn(BaseModel):
    message_id: str
    conversation_id: str
    value: str


@app.post("/api/feedback")
def feedback(payload: FeedbackIn):
    if payload.value not in ("up", "down"):
        return JSONResponse({"error": "value must be up or down"}, status_code=400)
    do_store.set_feedback(payload.message_id, payload.conversation_id, payload.value)
    return {"ok": True, "feedback": do_store.feedback_counts()}


@app.get("/api/evals")
def evals():
    return gateway.stats(do_store.feedback_counts())


@app.get("/api/audit")
def audit():
    return cf.admin_audit()

# ── access & permissions ───────────────────────────────────────────────

@app.get("/api/permissions")
def get_permissions():
    return permissions.token_state()


class TemplateIn(BaseModel):
    template: str


@app.post("/api/permissions/template")
def set_template(payload: TemplateIn):
    try:
        permissions.apply_template(payload.template)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return permissions.token_state()


class CustomIn(BaseModel):
    granted: list[str]


@app.post("/api/permissions/custom")
def set_custom(payload: CustomIn):
    permissions.set_custom(payload.granted)
    return permissions.token_state()


class WriteLockIn(BaseModel):
    enabled: bool


@app.post("/api/permissions/write-lock")
def set_write_lock(payload: WriteLockIn):
    permissions.set_write_lock(payload.enabled)
    return permissions.token_state()


# ── export generated code (take-home flow) ─────────────────────────────

EXPORTS: dict[str, dict] = {}
EXPORT_TTL_SECONDS = 36 * 3600


class ExportIn(BaseModel):
    project_name: str
    files: dict[str, str]
    conversation_id: str | None = None


@app.post("/api/export")
def export_code(payload: ExportIn):
    now = time.time()
    for k in [k for k, v in EXPORTS.items() if now > v["expires_at"]]:
        EXPORTS.pop(k)
    total = sum(len(v.encode()) for v in payload.files.values())
    if len(payload.files) > 50 or total > 2 * 1024 * 1024 or any(
            len(v.encode()) > 100 * 1024 for v in payload.files.values()):
        return JSONResponse(
            {"error": "Export is limited to 50 files, 100 KB per file and 2 MB total."},
            status_code=400)

    export_id = uuid.uuid4().hex[:8]
    credential = "ro_" + uuid.uuid4().hex
    EXPORTS[export_id] = {
        "project_name": payload.project_name,
        "files": payload.files,
        "expires_at": now + EXPORT_TTL_SECONDS,
        "credential": credential,
        "credential_expires_at": now + 3600,
        "host": "exports.nbody-agent.invalid",
    }
    do_store.add_message(payload.conversation_id or "-", "system",
                         f"Exported project {payload.project_name}")
    # NOTE: the clone command is never returned here — it must be fetched on demand
    return {"export_id": export_id,
            "project_name": payload.project_name,
            "files": sorted(payload.files),
            "expires_in_seconds": EXPORT_TTL_SECONDS}


@app.get("/api/export/{export_id}/clone-command")
def clone_command(export_id: str):
    """Fresh credential on demand — never stored in the transcript or model context."""
    exp = EXPORTS.get(export_id)
    if exp is None:
        return JSONResponse({"error": "export not found"}, status_code=404)
    now = time.time()
    if now > exp["expires_at"]:
        return JSONResponse({"error": "this export has expired"}, status_code=410)
    if now > exp.get("credential_expires_at", exp["expires_at"]):
        return JSONResponse({"error": "clone credential has expired"}, status_code=410)
    remaining = int(max(0, exp["credential_expires_at"] - now))
    cmd = (f"git clone https://{exp['credential']}@{exp['host']}/"
           f"{exp['project_name']}.git {exp['project_name']}")
    return {"command": cmd, "credential_expires_in_seconds": remaining}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("NBODY_PORT", "8080"))
    print(f"[orbit] Orbit Console -> http://0.0.0.0:{port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)