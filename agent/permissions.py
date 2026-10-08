"""Access & permissions — NBody Agent's "Manage access and permissions" surface.

  * templates: Full access / Read only / Custom (per-permission read+write toggles)
  * an API token created on the user's behalf, scoped to the grant, rotated on change
  * four areas that can never be written, whatever the token holds
  * an account-admin write lock that disables every mutation
"""
from __future__ import annotations

import threading

import cf

# Full access = every known permission, read and write. Writes still require
# per-change approval inside the conversation.
ALL_PERMISSIONS: list[str] = []

TEMPLATES = {
    "full": "Full access — read your resources and propose changes. Every write still "
            "requires your approval before it executes.",
    "read_only": "Read only — read and inspect your resources. NBody Agent cannot change "
                 "anything.",
    "custom": "Custom — choose individual permissions yourself.",
}

# Never writable, no matter which template is selected (documented guarantee).
NEVER_WRITABLE = {
    "account_settings": "Account settings",
    "account_membership": "Account membership",
    "billing": "Billing",
    "api_tokens": "API tokens",
}

_lock = threading.Lock()
_state = {
    "template": "full",
    "granted": {},          # permission -> bool
    "write_locked": False,  # account-admin kill switch
    "token_name": None,
    "enabled": True,
}


def load_catalogue():
    """Pull the permission catalogue from the API so both sides agree."""
    cfg = cf.admin_config()
    global ALL_PERMISSIONS
    ALL_PERMISSIONS = sorted(cfg["permissions"].keys())
    for p in ALL_PERMISSIONS:
        _state["granted"].setdefault(p, False)
    for p in ALL_PERMISSIONS:
        _state["granted"][p] = True          # full access by default
    _state["write_locked"] = bool(cfg.get("write_locked", False))


def _scopes_for_state() -> list[str]:
    template = _state["template"]
    if template == "read_only":
        return [p for p in ALL_PERMISSIONS if p.endswith(":read")]
    if template == "custom":
        return [p for p in ALL_PERMISSIONS if _state["granted"].get(p)]
    return list(ALL_PERMISSIONS)


def rotate_token() -> str:
    """Create a fresh scoped token and retire the old one (docs behaviour)."""
    previous = _state.get("token_name")
    rec = cf.admin_create_token(_scopes_for_state())
    cf.set_token(rec["secret"], rec["name"])
    _state["token_name"] = rec["name"]
    if previous:
        try:
            cf.admin_delete_token(previous)   # old token is deleted after the new one exists
        except Exception:
            pass
    return rec["name"]


def apply_template(template: str):
    if template not in TEMPLATES:
        raise ValueError(f"unknown template: {template}")
    with _lock:
        _state["template"] = template
        if template == "full":
            for p in ALL_PERMISSIONS:
                _state["granted"][p] = True
        elif template == "read_only":
            for p in ALL_PERMISSIONS:
                _state["granted"][p] = p.endswith(":read")
    rotate_token()


def set_custom(granted: list[str]):
    with _lock:
        _state["template"] = "custom"
        for p in ALL_PERMISSIONS:
            _state["granted"][p] = p in set(granted)
    rotate_token()


def set_write_lock(enabled: bool):
    """Simulates the account administrator disabling writes."""
    cf.admin_set_write_lock(enabled)
    _state["write_locked"] = enabled


def token_state() -> dict:
    """What the assistant is allowed to do right now."""
    scopes = set(_scopes_for_state())
    return {
        "template": _state["template"],
        "template_help": TEMPLATES[_state["template"]],
        "granted": dict(_state["granted"]),
        "scopes": sorted(scopes),
        "write_locked": _state["write_locked"],
        "token_name": _state["token_name"],
        "never_writable": NEVER_WRITABLE,
        "catalogue": {p: _describe(p) for p in ALL_PERMISSIONS},
    }


def _describe(perm: str) -> str:
    try:
        return cf.admin_config()["permissions"][perm]
    except Exception:
        return perm


def _ensure_catalogue():
    """The catalogue comes from the API; fetch it once if we have not yet."""
    if not ALL_PERMISSIONS:
        try:
            load_catalogue()
        except Exception:
            pass


def can_read(permission: str | None) -> bool:
    if permission is None:
        return True                      # diagnostics don't touch the account
    _ensure_catalogue()
    if _state["write_locked"] and permission.endswith(":write"):
        return False
    return permission in set(_scopes_for_state())


def write_available() -> bool:
    return not _state["write_locked"]


def available_tools() -> list[str]:
    """Tool names the model may see, filtered by the current grant."""
    import mcp

    _ensure_catalogue()
    out = []
    for name, spec in mcp.ALL_TOOLS.items():
        perm = spec["permission"]
        if perm is None:
            out.append(name)
        elif spec["kind"] == mcp.READ and can_read(perm):
            out.append(name)
        elif spec["kind"] == mcp.WRITE and can_read(perm) and write_available():
            out.append(name)
    return out