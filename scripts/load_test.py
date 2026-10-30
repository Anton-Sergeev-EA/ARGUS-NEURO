"""Small load test for a running ARGUS-NEURO: latency percentiles and WebSocket fan-out.

    python scripts/load_test.py --base http://127.0.0.1:8000 --duration 20
    python scripts/load_test.py --base https://localhost:8443 --auth operator:PASSWORD --insecure

Measures what it sends and nothing else: results describe this host and this run only.
"""

from __future__ import annotations

import argparse
import asyncio
import ssl
import statistics
import time
from base64 import b64encode

import httpx
import websockets

PATHS = ("/api/health", "/api/fleet", "/api/battery/example")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(q * len(ordered)), len(ordered) - 1)] if ordered else 0.0


async def worker(
    client: httpx.AsyncClient, path: str, stop: float, out: list[float], codes: dict
) -> None:
    while time.monotonic() < stop:
        started = time.perf_counter()
        try:
            r = await client.get(path)
            code = r.status_code
        except httpx.HTTPError:
            code = 0
        out.append((time.perf_counter() - started) * 1000)
        codes[code] = codes.get(code, 0) + 1


async def listener(
    url: str, headers: dict, ctx: ssl.SSLContext | None, stop: float, got: list[int]
) -> None:
    count = 0
    try:
        async with websockets.connect(url, additional_headers=headers, ssl=ctx) as ws:
            while time.monotonic() < stop:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                    count += 1
                except asyncio.TimeoutError:
                    continue
    except Exception:  # noqa: BLE001 - a failed client is a result, not a crash
        count = -1
    got.append(count)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--auth", default="", help="user:password for HTTP Basic")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--concurrency", type=int, default=8, help="per path")
    parser.add_argument("--ws-clients", type=int, default=20)
    args = parser.parse_args()
    headers = {}
    if args.auth:
        headers["Authorization"] = "Basic " + b64encode(args.auth.encode()).decode()
    ctx = ssl._create_unverified_context() if args.insecure else None  # noqa: SLF001
    ws_url = args.base.replace("http", "ws", 1) + "/ws/telemetry"
    stop = time.monotonic() + args.duration
    results: dict[str, tuple[list[float], dict]] = {p: ([], {}) for p in PATHS}
    got: list[int] = []
    async with httpx.AsyncClient(
        base_url=args.base, headers=headers, verify=not args.insecure, timeout=15
    ) as client:
        tasks = [
            worker(client, p, stop, *results[p])
            for p in PATHS
            for _ in range(args.concurrency)
        ]
        tasks += [
            listener(ws_url, headers, ctx, stop, got) for _ in range(args.ws_clients)
        ]
        await asyncio.gather(*tasks)
    print(f"duration {args.duration:.0f}s, {args.concurrency} workers per path")
    for path, (lat, codes) in results.items():
        print(
            f"{path:24s} n={len(lat):6d} rps={len(lat) / args.duration:7.1f} "
            f"p50={statistics.median(lat):7.1f}ms p95={percentile(lat, 0.95):7.1f}ms "
            f"p99={percentile(lat, 0.99):7.1f}ms codes={codes}"
        )
    ok = [g for g in got if g >= 0]
    print(
        f"websocket: {len(ok)}/{len(got)} clients connected, "
        f"messages per client min={min(ok, default=0)} max={max(ok, default=0)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
