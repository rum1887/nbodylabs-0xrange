"""Durable-Objects equivalent: per-conversation storage + the write approval gate.

One row per conversation, one row per message, and — the important part — every
write the assistant proposes is persisted as a *proposal* with status
`pending`. Nothing executes until a human approves it in the UI. Proposals also
record the state before the change so the assistant can later propose an undo.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

DB_PATH = os.environ.get("NBODY_DB", "/data/nbody_state.db")

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created TEXT,
    updated TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    role TEXT,
    content TEXT,
    payload TEXT,
    created TEXT
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    tool TEXT,
    args TEXT,
    summary TEXT,
    rationale TEXT,
    status TEXT,          -- pending | approved | rejected | executed | failed
    result TEXT,
    before_state TEXT,
    created TEXT,
    decided TEXT
);
CREATE TABLE IF NOT EXISTS changes (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    proposal_id TEXT,
    tool TEXT,
    args TEXT,
    before_state TEXT,
    summary TEXT,
    created TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    value TEXT,           -- up | down
    created TEXT
);
"""


def db() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ── conversations (history) ────────────────────────────────────────────

def new_conversation(title: str | None = None) -> str:
    cid = _new_id()
    with _lock:
        db().execute(
            "INSERT INTO conversations (id, title, created, updated) VALUES (?,?,?,?)",
            (cid, title or "New conversation", _now(), _now()))
        db().commit()
    return cid


def list_conversations() -> list[dict]:
    rows = db().execute(
        "SELECT id, title, created, updated FROM conversations ORDER BY updated DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def touch(conversation_id: str, title: str | None = None):
    with _lock:
        if title:
            db().execute("UPDATE conversations SET title=?, updated=? WHERE id=?",
                         (title, _now(), conversation_id))
        else:
            db().execute("UPDATE conversations SET updated=? WHERE id=?",
                         (_now(), conversation_id))
        db().commit()


def add_message(conversation_id: str, role: str, content: str, payload: dict | None = None):
    mid = _new_id()
    with _lock:
        db().execute(
            "INSERT INTO messages (id, conversation_id, role, content, payload, created)"
            " VALUES (?,?,?,?,?,?)",
            (mid, conversation_id, role, content, json.dumps(payload or {}), _now()))
        db().execute("UPDATE conversations SET updated=? WHERE id=?", (_now(), conversation_id))
        db().commit()
    return mid


def get_messages(conversation_id: str, limit: int = 100) -> list[dict]:
    rows = db().execute(
        "SELECT id, role, content, payload, created FROM messages WHERE conversation_id=?"
        " ORDER BY created ASC, rowid ASC LIMIT ?", (conversation_id, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"] or "{}")
        out.append(d)
    return out

# ── the approval gate ──────────────────────────────────────────────────

def propose(conversation_id: str, tool: str, args: dict, summary: str,
            rationale: str = "", before_state: dict | None = None) -> dict:
    """Persist a proposed write. It does NOT execute."""
    pid = _new_id()
    with _lock:
        db().execute(
            "INSERT INTO proposals (id, conversation_id, tool, args, summary, rationale,"
            " status, before_state, created) VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, conversation_id, tool, json.dumps(args), summary, rationale,
             "pending", json.dumps(before_state or {}), _now()))
        db().commit()
    return get_proposal(pid)


def get_proposal(proposal_id: str) -> dict | None:
    row = db().execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    return _proposal_row(row) if row else None


def _proposal_row(row) -> dict:
    d = dict(row)
    d["args"] = json.loads(d["args"] or "{}")
    d["before_state"] = json.loads(d["before_state"] or "{}")
    return d


def list_proposals(conversation_id: str | None = None, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM proposals"
    where, params = [], []
    if conversation_id:
        where.append("conversation_id=?")
        params.append(conversation_id)
    if status:
        where.append("status=?")
        params.append(status)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created DESC"
    return [_proposal_row(r) for r in db().execute(q, params).fetchall()]


def decide(proposal_id: str, status: str, result: dict | None = None) -> dict | None:
    with _lock:
        db().execute("UPDATE proposals SET status=?, result=?, decided=? WHERE id=?",
                     (status, json.dumps(result or {}), _now(), proposal_id))
        db().commit()
    return get_proposal(proposal_id)


def record_change(conversation_id: str, proposal_id: str, tool: str, args: dict,
                  before_state: dict, summary: str) -> str:
    cid = _new_id()
    with _lock:
        db().execute(
            "INSERT INTO changes (id, conversation_id, proposal_id, tool, args,"
            " before_state, summary, created) VALUES (?,?,?,?,?,?,?,?)",
            (cid, conversation_id, proposal_id, tool, json.dumps(args),
             json.dumps(before_state), summary, _now()))
        db().commit()
    return cid


def list_changes(conversation_id: str | None = None) -> list[dict]:
    if conversation_id:
        rows = db().execute("SELECT * FROM changes WHERE conversation_id=? ORDER BY created",
                            (conversation_id,)).fetchall()
    else:
        rows = db().execute("SELECT * FROM changes ORDER BY created").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["args"] = json.loads(d["args"] or "{}")
        d["before_state"] = json.loads(d["before_state"] or "{}")
        out.append(d)
    return out


# ── feedback (thumbs up/down → eval signals) ───────────────────────────

def set_feedback(message_id: str, conversation_id: str, value: str) -> bool:
    with _lock:
        db().execute(
            "INSERT INTO feedback (message_id, conversation_id, value, created)"
            " VALUES (?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET value=excluded.value",
            (message_id, conversation_id, value, _now()))
        db().commit()
    return True


def feedback_counts() -> dict:
    rows = db().execute("SELECT value, COUNT(*) c FROM feedback GROUP BY value").fetchall()
    return {r["value"]: r["c"] for r in rows}


def conversation_title(conversation_id: str) -> str | None:
    row = db().execute("SELECT title FROM conversations WHERE id=?",
                       (conversation_id,)).fetchone()
    return row["title"] if row else None