from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from argus.api import server


class FakeSocket:
    def __init__(self, blocked: bool = False) -> None:
        self.messages: list[str] = []
        self.blocked = blocked
        self.received = asyncio.Event()
        self.closed = asyncio.Event()

    async def accept(self) -> None:
        pass

    async def send_text(self, message: str) -> None:
        if self.blocked:
            await asyncio.Event().wait()
        self.messages.append(message)
        self.received.set()

    async def close(self) -> None:
        self.closed.set()


def test_slow_client_does_not_block_healthy_client() -> None:
    async def scenario() -> None:
        manager = server.ConnectionManager(send_timeout=0.05)
        slow, fast = FakeSocket(True), FakeSocket()
        await manager.connect(slow)
        await manager.connect(fast)
        await manager.broadcast({"tick": 1})
        await asyncio.wait_for(fast.received.wait(), 1)
        await asyncio.wait_for(slow.closed.wait(), 1)
        assert fast.messages == ['{"tick": 1}']
        assert manager.connected_count == 1
        await manager.close()
        assert manager.connected_count == 0

    asyncio.run(scenario())


def test_pending_snapshots_are_bounded_and_disconnect_is_safe() -> None:
    async def scenario() -> None:
        manager = server.ConnectionManager()
        client = FakeSocket()
        await manager.connect(client)
        for value in range(100):
            await manager.broadcast({"tick": value})
        assert manager._queues[client].qsize() == 1
        await asyncio.wait_for(client.received.wait(), 1)
        assert json.loads(client.messages[-1])["tick"] == 99
        await asyncio.gather(
            manager.disconnect(client), manager.broadcast({"tick": 100})
        )
        await manager.close()

    asyncio.run(scenario())


class FakeFleet:
    model_backed = True

    def tick(self) -> dict[str, Any]:
        raise RuntimeError("test producer failure")


def test_health_detects_producer_failure_and_stale_data() -> None:
    async def scenario() -> None:
        state = server.ServiceState(
            FakeFleet(), server.ConnectionManager(), asyncio.Event()
        )
        server.app.state.telemetry = state
        state.task = asyncio.create_task(server._broadcast_loop(state))
        await state.task
        response = await server.health()
        assert response.status_code == 503
        assert json.loads(response.body)["error"] == "RuntimeError"
        state.task = asyncio.create_task(asyncio.Event().wait())
        state.last_tick = time.monotonic() - 100
        assert (await server.health()).status_code == 503
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass
        del server.app.state.telemetry

    asyncio.run(scenario())
