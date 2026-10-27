"""Small in-memory sliding-window limiter for the expensive battery routes."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

DEFAULT_LIMIT = 60
WINDOW_SECONDS = 60.0
MAX_CLIENTS = 1024


class SlidingWindow:
    def __init__(self, limit: int, window: float = WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client: str, now: float | None = None) -> float | None:
        """Return seconds to wait, or ``None`` if the request is allowed."""
        now = time.monotonic() if now is None else now
        if len(self._hits) > MAX_CLIENTS:
            self._hits = defaultdict(
                deque,
                {
                    k: v
                    for k, v in self._hits.items()
                    if v and now - v[-1] < self.window
                },
            )
        hits = self._hits[client]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return self.window - (now - hits[0])
        hits.append(now)
        return None


LIMITER = SlidingWindow(int(os.environ.get("ARGUS_BATTERY_RATE_LIMIT", DEFAULT_LIMIT)))


async def limit_requests(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    wait = LIMITER.check(client)
    if wait is not None:
        raise HTTPException(
            429,
            detail="rate_limited",
            headers={"Retry-After": str(max(1, int(wait) + 1))},
        )
