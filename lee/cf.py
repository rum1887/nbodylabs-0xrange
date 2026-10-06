"""Client for the platform API (mock) — the account plane Nimbus operates on.

Holds the scoped token that stands in for the API token Nimbus creates on
the user's behalf, and surfaces permission errors verbatim so the assistant can
tell the user *why* a call failed.
"""
from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("CF_API_URL", "http://cf-mock:5000").rstrip("/")

# Scoped token, created/rotated by permissions.py and handed to Nimbus here.
TOKEN: str | None = None
TOKEN_NAME: str | None = None


def set_token(secret: str, name: str | None = None):
    global TOKEN, TOKEN_NAME
    TOKEN = secret
    TOKEN_NAME = name


class APIError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _headers() -> dict:
    if not TOKEN:
        raise APIError(401, "Nimbus has no API token. Grant access first.")
    return {"Authorization": f"Bearer {TOKEN}"}


def call(method: str, path: str, **kw) -> object:
    try:
        resp = requests.request(method, BASE_URL + path, headers=_headers(), timeout=20, **kw)
    except requests.RequestException as exc:
        raise APIError(0, f"Cannot reach the platform API: {exc}") from exc
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(resp.status_code, str(detail))
    return resp.json() if resp.content else {}


# ── reads ──────────────────────────────────────────────────────────────

def list_zones():
    return call("GET", "/zones")


def get_zone(zone_id: str):
    return call("GET", f"/zones/{zone_id}")


def get_settings(zone_id: str):
    return call("GET", f"/zones/{zone_id}/settings")


def list_dns_records(zone_id: str):
    return call("GET", f"/zones/{zone_id}/dns-records")


def list_security_rules(zone_id: str):
    return call("GET", f"/zones/{zone_id}/security-rules")


def list_cache_rules(zone_id: str):
    return call("GET", f"/zones/{zone_id}/cache-rules")


def get_analytics(zone_id: str):
    return call("GET", f"/zones/{zone_id}/analytics")


def list_workers():
    return call("GET", "/workers")


def get_worker(script: str):
    return call("GET", f"/workers/{script}")


def list_worker_secrets(script: str):
    return call("GET", f"/workers/{script}/secrets")


def list_r2_buckets():
    return call("GET", "/r2/buckets")


def list_tunnels():
    return call("GET", "/tunnels")


def get_account():
    return call("GET", "/account")


# ── writes (only ever called from the approval gate) ────────────────────

def create_dns_record(zone_id: str, record: dict):
    return call("POST", f"/zones/{zone_id}/dns-records", json=record)


def update_dns_record(zone_id: str, rec_id: str, patch: dict):
    return call("PATCH", f"/zones/{zone_id}/dns-records/{rec_id}", json=patch)


def delete_dns_record(zone_id: str, rec_id: str):
    return call("DELETE", f"/zones/{zone_id}/dns-records/{rec_id}")


def update_settings(zone_id: str, settings: dict):
    return call("PATCH", f"/zones/{zone_id}/settings", json={"settings": settings})


def update_security_rule(zone_id: str, rule_id: str, patch: dict):
    return call("PATCH", f"/zones/{zone_id}/security-rules/{rule_id}", json=patch)


def update_cache_rule(zone_id: str, rule_id: str, patch: dict):
    return call("PATCH", f"/zones/{zone_id}/cache-rules/{rule_id}", json=patch)


def open_support_case(body: dict):
    return call("POST", "/support/cases", json=body)


# ── unauthenticated (diagnostics / navigation) ─────────────────────────

def dns_lookup(domain: str):
    return requests.get(f"{BASE_URL}/diagnostics/dns-lookup",
                        params={"domain": domain}, timeout=20).json()


def check_certificate(domain: str):
    return requests.get(f"{BASE_URL}/diagnostics/certificate",
                        params={"domain": domain}, timeout=20).json()


def whois(domain: str):
    return requests.get(f"{BASE_URL}/diagnostics/whois",
                        params={"domain": domain}, timeout=20).json()


def dashboard_pages():
    return requests.get(f"{BASE_URL}/dashboard/pages", timeout=20).json()


def support_info():
    return requests.get(f"{BASE_URL}/support", timeout=20).json()


# ── account admin controls (stand in for the dashboard) ────────────────

def admin_create_token(scopes: list[str]) -> dict:
    resp = requests.post(f"{BASE_URL}/admin/tokens", json={"scopes": scopes}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def admin_delete_token(name: str) -> dict:
    return requests.delete(f"{BASE_URL}/admin/tokens/{name}", timeout=20).json()


def admin_set_write_lock(enabled: bool) -> dict:
    return requests.post(f"{BASE_URL}/admin/write-lock", json={"enabled": enabled},
                         timeout=20).json()


def admin_audit() -> list:
    return requests.get(f"{BASE_URL}/admin/audit", timeout=20).json()


def admin_config() -> dict:
    return requests.get(f"{BASE_URL}/admin/config", timeout=20).json()


def health() -> bool:
    try:
        requests.get(f"{BASE_URL}/admin/config", timeout=5)
        return True
    except requests.RequestException:
        return False