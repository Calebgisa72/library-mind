"""Standalone AmaliAI connectivity / key diagnostic.

Run from the project root:  python scripts/check_amaliai.py

Loads your real Settings (.env), prints a masked fingerprint of the key that
actually loaded, then makes a live embeddings call to EACH candidate gateway
(production + dev/training) using the exact headers the app uses
(X-Api-Key + Provider). It prints the HTTP status for each so you can tell,
unambiguously, whether the 401 is a key problem, a wrong-environment problem,
or something else.

Exit codes: 0 = at least one host returned 200, 1 = none did, 2 = setup error.
"""

from __future__ import annotations

import sys

import httpx

try:
    from app.core.settings import get_settings
except Exception as exc:  # pragma: no cover
    print(f"[setup error] could not import settings: {exc}")
    sys.exit(2)

# Candidate gateways to try the SAME key against. The first is whatever your
# .env points at; the rest are well-known AmaliAI environments. A key issued
# for one environment is rejected by the others.
EXTRA_HOSTS = [
    "https://ai-api.amalitech.org/api/v2/public/v1",       # production
    "https://ai-api.amalitech-dev.net/api/v2/public/v1",   # dev / training
]


def _mask(secret: str) -> str:
    if not secret:
        return "<EMPTY>"
    if len(secret) <= 8:
        return f"<len={len(secret)}> {secret[0]}***"
    return f"<len={len(secret)}> {secret[:4]}...{secret[-4:]}"


def _try(base_url: str, key: str, model: str) -> int:
    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {"X-Api-Key": key, "Provider": "openai", "Content-Type": "application/json"}
    payload = {"model": model, "input": ["hello"]}
    print(f"\n--- POST {url}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        print(f"    [network error] {exc}")
        return -1
    print(f"    HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        dim = len(data.get("data", [{}])[0].get("embedding", []))
        print(f"    [OK] embedding dimension = {dim}")
        print(f"    >>> THIS is the gateway your key works on. Set AMALIAI_BASE_URL={base_url}")
    else:
        print(f"    body: {resp.text[:300]}")
    return resp.status_code


def main() -> int:
    s = get_settings()
    key = (s.amaliai_api_key or "").strip()
    model = s.amaliai_embedding_model

    print("=== AmaliAI diagnostic ===")
    print(f"X-Api-Key       : {_mask(key)}")
    print(f"embedding model : {model}")
    print(f".env base_url   : {s.amaliai_base_url}")
    print("provider header : openai")

    if not key:
        print("[FAIL] AMALIAI_API_KEY is empty — check your .env / launch directory.")
        return 2

    # Build the ordered, de-duplicated list of hosts to try.
    hosts: list[str] = []
    for h in [s.amaliai_base_url, *EXTRA_HOSTS]:
        h = h.rstrip("/")
        if h not in hosts:
            hosts.append(h)

    statuses = {h: _try(h, key, model) for h in hosts}

    print("\n=== summary ===")
    ok = [h for h, st in statuses.items() if st == 200]
    if ok:
        print(f"Key is VALID on: {ok[0]}")
        print("Point AMALIAI_BASE_URL there, hard-restart the server, then seed and query.")
        return 0

    if all(st == 401 for st in statuses.values()):
        print("Key returned 401 on EVERY environment tested.")
        print("Headers/URL are correct, so the key string itself is not active anywhere")
        print("we tried. Get a fresh key from the Amalitech *training* portal, or confirm")
        print("the correct gateway host for your account with your trainer.")
    else:
        print("Mixed/other results — see per-host output above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
