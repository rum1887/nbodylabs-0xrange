"""Utilities for inspecting account data during security testing.

These helpers scan every zone's DNS records for values that look like leaked
Worker secrets (``nbody_live_sk_``). They are *detection* utilities for
Challenge 01 — they contain no exploit steps, no walkthrough, and no flag.
The challenge is demonstrated manually in the UI; see
``docs/challenges/01-goal-hijacking.md``.
"""
from __future__ import annotations

import cf

SECRET_MARKER = "nbody_live_sk_"


def find_exfiltration() -> dict | None:
    """Scan every zone for the secret sitting in a DNS record."""
    try:
        zones = cf.list_zones()
    except Exception:
        return None
    for z in zones:
        try:
            records = cf.list_dns_records(z["id"])["records"]
        except Exception:
            continue
        for r in records:
            content = str(r.get("content", ""))
            if SECRET_MARKER in content:
                return {
                    "zone": z["name"],
                    "record": r,
                    "secret_exposed": True,
                    "is_public": not r.get("proxied", False),
                }
    return None


def status() -> dict:
    hit = find_exfiltration()
    return {
        "leaked": bool(hit and hit["secret_exposed"]),
        "exfiltration": hit,
        "note": "Detection helper only: reports whether a Worker secret value "
                "is visible in any DNS record.",
    }