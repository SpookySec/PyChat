from __future__ import annotations

import time
from asyncio import StreamWriter
from dataclasses import dataclass, field
from typing import Iterable

from shared.protocol import BasePacket


@dataclass
class ServerState:
    _writers: dict[StreamWriter, str] = field(default_factory=dict)
    _last_seen: dict[StreamWriter, float] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.monotonic)
    _connections_total: int = 0
    _disconnects_total: int = 0
    _messages_total: int = 0

    def add(self, writer: StreamWriter, username: str) -> None:
        self._writers[writer] = username
        self._last_seen[writer] = time.monotonic()
        self._connections_total += 1

    def remove(self, writer: StreamWriter) -> str | None:
        self._last_seen.pop(writer, None)
        username = self._writers.pop(writer, None)
        if username is not None:
            self._disconnects_total += 1
        return username

    def username_taken(self, username: str) -> bool:
        return username in self._writers.values()

    def get_username(self, writer: StreamWriter) -> str | None:
        return self._writers.get(writer)

    def users(self) -> list[str]:
        return sorted(self._writers.values())

    def writers(self) -> Iterable[StreamWriter]:
        return list(self._writers.keys())

    def touch(self, writer: StreamWriter) -> None:
        if writer in self._writers:
            self._last_seen[writer] = time.monotonic()

    def last_seen(self, writer: StreamWriter) -> float | None:
        return self._last_seen.get(writer)

    def record_message(self) -> None:
        self._messages_total += 1

    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def stats_snapshot(self) -> dict[str, int | float]:
        return {
            "uptime": self.uptime_seconds(),
            "active_users": len(self._writers),
            "connections": self._connections_total,
            "disconnects": self._disconnects_total,
            "messages": self._messages_total,
        }

    async def send_packet(self, writer: StreamWriter, packet: BasePacket) -> bool:
        try:
            writer.write(packet.to_wire().encode())
            await writer.drain()
            return True
        except Exception:
            return False

    async def broadcast(self, packet: BasePacket) -> list[StreamWriter]:
        dead_writers: list[StreamWriter] = []
        for writer in list(self._writers.keys()):
            ok = await self.send_packet(writer, packet)
            if not ok:
                dead_writers.append(writer)
        return dead_writers
