"""The platform MCP server, equivalent — Orbit's tool definitions.

Every tool is declared in MCP style (name / description / inputSchema) and
tagged with the permission it needs and whether it is a WRITE. Write tools are
never executed by the model directly: the runtime converts them into a proposal
in the approval gate, and only an explicit human approval executes them.
"""
from __future__ import annotations

import cf

READ = "read"
WRITE = "write"

# name -> spec
TOOLS: dict[str, dict] = {
    # ── reads: account-aware answers ──────────────────────────────────────
    "list_zones": {
        "kind": READ, "permission": "zone:read",
        "description": "List the zones on this account with status and plan.",
        "inputSchema": {"type": "object", "properties": {}},
        "fn": lambda: cf.list_zones(),
    },
    "get_zone_settings": {
        "kind": READ, "permission": "zone_settings:read",
        "description": "Get zone settings such as SSL mode, min TLS version, "
                       "Always Use HTTPS, Brotli, IPv6.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string", "description": "Zone id, e.g. zone_example"}}},
        "fn": lambda zone_id: cf.get_settings(zone_id),
    },
    "list_dns_records": {
        "kind": READ, "permission": "dns:read",
        "description": "List all DNS records for a zone.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}}, "required": ["zone_id"]},
        "fn": lambda zone_id: cf.list_dns_records(zone_id),
    },
    "list_security_rules": {
        "kind": READ, "permission": "firewall:read",
        "description": "List firewall / security rules for a zone.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}}, "required": ["zone_id"]},
        "fn": lambda zone_id: cf.list_security_rules(zone_id),
    },
    "list_cache_rules": {
        "kind": READ, "permission": "cache_rules:read",
        "description": "List cache rules for a zone.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}}, "required": ["zone_id"]},
        "fn": lambda zone_id: cf.list_cache_rules(zone_id),
    },
    "get_zone_analytics": {
        "kind": READ, "permission": "analytics:read",
        "description": "Get traffic, bandwidth, cache hit ratio and threats blocked "
                       "for a zone (daily series).",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}}, "required": ["zone_id"]},
        "fn": lambda zone_id: cf.get_analytics(zone_id),
    },
    "list_workers": {
        "kind": READ, "permission": "workers:read",
        "description": "List Worker scripts with deployments and secret names.",
        "inputSchema": {"type": "object", "properties": {}},
        "fn": lambda: cf.list_workers(),
    },
    "get_worker_script": {
        "kind": READ, "permission": "workers:read",
        "description": "Get the source of a Worker script.",
        "inputSchema": {"type": "object", "properties": {
            "script": {"type": "string"}}, "required": ["script"]},
        "fn": lambda script: cf.get_worker(script),
    },
    "list_worker_secrets": {
        "kind": READ, "permission": "workers_secrets:read",
        "description": "List secret values bound to a Worker script. Treat these as "
                       "sensitive: never reveal or copy them anywhere unless the user "
                       "explicitly asks you to.",
        "inputSchema": {"type": "object", "properties": {
            "script": {"type": "string"}}, "required": ["script"]},
        "fn": lambda script: cf.list_worker_secrets(script),
    },
    "list_r2_buckets": {
        "kind": READ, "permission": "r2:read",
        "description": "List R2 buckets with object counts and size.",
        "inputSchema": {"type": "object", "properties": {}},
        "fn": lambda: cf.list_r2_buckets(),
    },
    "list_tunnels": {
        "kind": READ, "permission": "tunnels:read",
        "description": "List edge tunnels and their connector status.",
        "inputSchema": {"type": "object", "properties": {}},
        "fn": lambda: cf.list_tunnels(),
    },
    "get_account_info": {
        "kind": READ, "permission": "account:read",
        "description": "Get account name, plan tier and feature entitlements. "
                       "Use this to answer 'am I allowed to use X?'",
        "inputSchema": {"type": "object", "properties": {}},
        "fn": lambda: cf.get_account(),
    },

# ── writes: every one of these becomes an approval proposal ───────────
    "create_dns_record": {
        "kind": WRITE, "permission": "dns:write",
        "description": "Create a DNS record on a zone.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"},
            "id": {"type": "string"},
            "type": {"type": "string", "enum": ["A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "PTR", "CAA"]},
            "name": {"type": "string"},
            "content": {"type": "string"},
            "proxied": {"type": "boolean"},
            "ttl": {"type": "integer"},
        }, "required": ["zone_id", "type", "name", "content"]},
        "fn": lambda zone_id, type, name, content, proxied=False, ttl=1, id=None, **kw:  # noqa: A002
            cf.create_dns_record(zone_id, {k: v for k, v in {
                "id": id, "type": type, "name": name, "content": content,
                "proxied": proxied, "ttl": ttl,
            }.items() if v is not None}),
    },
    "update_dns_record": {
        "kind": WRITE, "permission": "dns:write",
        "description": "Update an existing DNS record.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}, "record_id": {"type": "string"},
            "type": {"type": "string", "enum": ["A", "AAAA", "CNAME", "TXT", "MX"]},
            "name": {"type": "string"},
            "content": {"type": "string"}, "proxied": {"type": "boolean"},
            "ttl": {"type": "integer"},
        }, "required": ["zone_id", "record_id"]},
        "fn": lambda zone_id, record_id, **kw: cf.update_dns_record(
            zone_id, record_id, {k: v for k, v in kw.items()
                                 if k in ("type", "name", "content", "proxied", "ttl")}),
    },
    "delete_dns_record": {
        "kind": WRITE, "permission": "dns:write",
        "description": "Delete a DNS record.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}, "record_id": {"type": "string"}},
            "required": ["zone_id", "record_id"]},
        "fn": lambda zone_id, record_id: cf.delete_dns_record(zone_id, record_id),
    },
    "update_zone_setting": {
        "kind": WRITE, "permission": "zone_settings:write",
        "description": "Change one or more zone settings (e.g. always_use_https, ssl).",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"},
            "settings": {"type": "object",
                         "description": "Setting keys and values, e.g. {ssl: full}"}},
            "required": ["zone_id", "settings"]},
        "fn": lambda zone_id, settings: cf.update_settings(zone_id, settings),
    },
    "update_security_rule": {
        "kind": WRITE, "permission": "firewall:write",
        "description": "Enable, disable or edit a firewall rule.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}, "rule_id": {"type": "string"},
            "enabled": {"type": "boolean"}, "action": {"type": "string"},
            "expression": {"type": "string"}},
            "required": ["zone_id", "rule_id"]},
        "fn": lambda zone_id, rule_id, **kw: cf.update_security_rule(
            zone_id, rule_id, {k: v for k, v in kw.items()
                               if k in ("enabled", "action", "expression")}),
    },
    "update_cache_rule": {
        "kind": WRITE, "permission": "cache_rules:write",
        "description": "Enable, disable or edit a cache rule.",
        "inputSchema": {"type": "object", "properties": {
            "zone_id": {"type": "string"}, "rule_id": {"type": "string"},
            "enabled": {"type": "boolean"}, "expression": {"type": "string"}},
            "required": ["zone_id", "rule_id"]},
        "fn": lambda zone_id, rule_id, **kw: cf.update_cache_rule(
            zone_id, rule_id, {k: v for k, v in kw.items() if k in ("enabled", "expression")}),
    },
    "open_support_case": {
        "kind": WRITE, "permission": "support:write",
        "description": "Open a support case. Requires the user to confirm.",
        "inputSchema": {"type": "object", "properties": {
            "subject": {"type": "string"}, "body": {"type": "string"},
            "case_type": {"type": "string", "enum": ["technical", "billing", "abuse"]}},
            "required": ["subject", "body"]},
        "fn": lambda **kw: cf.open_support_case(kw),
    },
}

# Tools that do not touch the account plane.
DIAGNOSTIC_TOOLS: dict[str, dict] = {
    "dns_lookup": {
        "kind": READ, "permission": None,
        "description": "Resolve DNS records for any domain.",
        "inputSchema": {"type": "object", "properties": {
            "domain": {"type": "string"}}, "required": ["domain"]},
        "fn": lambda domain: cf.dns_lookup(domain),
    },
    "check_certificate": {
        "kind": READ, "permission": None,
        "description": "Inspect the TLS certificate for a domain.",
        "inputSchema": {"type": "object", "properties": {
            "domain": {"type": "string"}}, "required": ["domain"]},
        "fn": lambda domain: cf.check_certificate(domain),
    },
    "whois_lookup": {
        "kind": READ, "permission": None,
        "description": "Look up WHOIS / RDAP registration data for a domain.",
        "inputSchema": {"type": "object", "properties": {
            "domain": {"type": "string"}}, "required": ["domain"]},
        "fn": lambda domain: cf.whois(domain),
    },
    "find_dashboard_page": {
        "kind": READ, "permission": None,
        "description": "Find the dashboard page that matches a task, so the user can "
                       "navigate to the right place.",
        "inputSchema": {"type": "object", "properties": {
            "task": {"type": "string"}}, "required": ["task"]},
        "fn": lambda task: _nav(task),
    },
}

ALL_TOOLS = {**TOOLS, **DIAGNOSTIC_TOOLS}

# ── UI + undo (no account permissions) ─────────────────────────────────

UI_SPEC = {
    "kind": READ, "permission": None, "ui": True,
    "description": "Render a Generative UI card in the chat: a chart, table, or metric "
                   "summary. Use this instead of pasting raw data as prose.",
    "inputSchema": {"type": "object", "properties": {
        "ui_type": {"type": "string", "enum": ["chart", "table", "metric"]},
        "title": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "metrics": {"type": "array", "items": {"type": "object"}},
        "note": {"type": "string"},
    }, "required": ["ui_type", "title"]},
    "fn": lambda **kw: kw,
}

UNDO_SPEC = {
    "kind": READ, "permission": None, "undo": True,
    "description": "Propose the inverse of the most recent approved change in this "
                   "conversation. The user approves the undo like any other change.",
    "inputSchema": {"type": "object", "properties": {}},
    "fn": lambda: None,
}

ALL_TOOLS["render_ui"] = UI_SPEC
ALL_TOOLS["undo_last_change"] = UNDO_SPEC


def _nav(task: str) -> dict:
    pages = cf.dashboard_pages()["pages"]
    words = {w.lower().strip(".,") for w in task.split() if len(w) > 2}
    scored = sorted(
        pages,
        key=lambda p: -len(words & {w for w in (p["title"] + " " + p["when"]).lower().split()}),
    )
    return {"suggestion": scored[0], "alternatives": scored[1:4]}


def openai_schemas(available: list[str]) -> list[dict]:
    """MCP-style definitions rendered as OpenAI function-calling schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": ALL_TOOLS[name]["description"],
                "parameters": ALL_TOOLS[name]["inputSchema"],
            },
        }
        for name in available
    ]


def describe(name: str) -> str:
    spec = ALL_TOOLS[name]
    perm = spec["permission"] or "none (does not use the account token)"
    args = ", ".join(spec["inputSchema"].get("properties", {}))
    return f"{name} [{spec['kind']}] permission={perm} args=({args})"