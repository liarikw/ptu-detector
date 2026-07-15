from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException

MAX_PER_HOUR = int(os.getenv("PTU_MAX_PER_HOUR", "20"))
WINDOW_SECONDS = 3600

_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(request: Request) -> None:
    """Simple in-memory per-IP rate limit. Raises 429 if exceeded."""
    ip = _client_ip(request)
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= MAX_PER_HOUR:
        oldest = q[0]
        retry_after = int(WINDOW_SECONDS - (now - oldest))
        raise HTTPException(
            429,
            f"Chill! Limit is {MAX_PER_HOUR}/hour. Try again in ~{max(retry_after, 1)}s.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
    q.append(now)


def check_passcode(request: Request) -> None:
    """If PTU_PASSCODE is set, require it via ?passcode= or X-Passcode header."""
    expected = os.getenv("PTU_PASSCODE")
    if not expected:
        return
    provided = request.query_params.get("passcode") or request.headers.get("x-passcode")
    if provided != expected:
        raise HTTPException(401, "Passcode required.")
