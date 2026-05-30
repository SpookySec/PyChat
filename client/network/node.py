from __future__ import annotations

import asyncio
import contextlib
from asyncio import StreamReader, StreamWriter
from typing import Awaitable, Callable

from shared.protocol import (
    BasePacket,
    ConnectPacket,
    Packet,
    packet_from_json,
)

PacketHandler = Callable[[Packet], Awaitable[None]]


class ChatClient:
    def __init__(self, on_packet: PacketHandler) -> None:
        self._on_packet = on_packet
        self._reader: StreamReader | None = None
        self._writer: StreamWriter | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._writer is not None

    async def connect(self, host: str, port: int, username: str) -> None:
        self._reader, self._writer = await asyncio.open_connection(host, port)
        await self.send_packet(ConnectPacket(username=username))

    async def start_listening(self) -> None:
        if self._listen_task is None:
            self._listen_task = asyncio.create_task(self.listen_loop())

    async def send_packet(self, packet: BasePacket) -> None:
        async with self._lock:
            if self._writer is None:
                raise ConnectionError("Not connected")
            self._writer.write(packet.to_wire().encode())
            await self._writer.drain()

    async def listen_loop(self) -> None:
        if self._reader is None:
            raise ConnectionError("Not connected")
        while True:
            line = await self._reader.readline()
            if not line:
                break
            try:
                packet = packet_from_json(line.decode().strip())
            except Exception:
                continue
            await self._on_packet(packet)

    async def close(self) -> None:
        if self._listen_task is not None:
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task
            self._listen_task = None
        if self._writer is not None:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
            self._writer = None
            self._reader = None
