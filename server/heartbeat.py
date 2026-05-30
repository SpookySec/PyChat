from __future__ import annotations

import asyncio
import time
from asyncio import StreamWriter
from typing import Awaitable, Callable

from shared.protocol import BasePacket, PingPacket, UserLeftPacket
from .state import ServerState
from .daemon import close_writer


async def heartbeat_loop(
    state: ServerState,
    broadcast: Callable[[BasePacket], Awaitable[None]],
    interval: float = 5.0,
    timeout: float = 15.0,
) -> None:
    while True:
        await asyncio.sleep(interval)
        now = time.monotonic()
        dead_writers: list[StreamWriter] = []
        for writer in state.writers():
            last = state.last_seen(writer)
            if last is None or now - last > timeout:
                dead_writers.append(writer)
                continue
            ok = await state.send_packet(writer, PingPacket())
            if not ok:
                dead_writers.append(writer)
        for writer in dead_writers:
            username = state.remove(writer)
            await close_writer(writer)
            if username:
                await broadcast(UserLeftPacket(username=username))
