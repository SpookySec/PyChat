from __future__ import annotations

import time
from asyncio import StreamWriter
from dataclasses import dataclass, field
from typing import Iterable

from shared.protocol import BasePacket, HistoryItem, MessagePacket, UserInfo


@dataclass
class ServerState:
    _writers: dict[StreamWriter, str] = field(default_factory=dict)
    _last_seen: dict[StreamWriter, float] = field(default_factory=dict)
    _known_users: dict[str, bool] = field(default_factory=dict)
    _history: list[HistoryItem] = field(default_factory=list)
    _start_time: float = field(default_factory=time.monotonic)
    _connections_total: int = 0
    _disconnects_total: int = 0
    _messages_total: int = 0
    _history_limit: int = 200

    def add(self, writer: StreamWriter, username: str) -> None:
        self._writers[writer] = username
        self._last_seen[writer] = time.monotonic()
        self._known_users[username] = True
        self._connections_total += 1

    def remove(self, writer: StreamWriter) -> str | None:
        self._last_seen.pop(writer, None)
        username = self._writers.pop(writer, None)
        if username is not None:
            self._disconnects_total += 1
            self._known_users[username] = False
        return username

    def username_taken(self, username: str) -> bool:
        return username in self._writers.values()

    def get_username(self, writer: StreamWriter) -> str | None:
        return self._writers.get(writer)

    def users(self) -> list[str]:
        return sorted(self._writers.values())

    def user_list(self) -> list[UserInfo]:
        users = [
            UserInfo(username=name, online=is_online)
            for name, is_online in self._known_users.items()
        ]
        users.sort(key=lambda user: user.username.lower())
        return users

    def rename_user(self, old_username: str, new_username: str) -> None:
        if old_username in self._known_users:
            is_online = self._known_users.pop(old_username)
            self._known_users[new_username] = is_online

    def rename_writer(self, writer: StreamWriter, new_username: str) -> None:
        old_username = self._writers.get(writer)
        if old_username is None:
            return
        self._writers[writer] = new_username
        self.rename_user(old_username, new_username)

    def writers(self) -> Iterable[StreamWriter]:
        return list(self._writers.keys())

    def touch(self, writer: StreamWriter) -> None:
        if writer in self._writers:
            self._last_seen[writer] = time.monotonic()

    def last_seen(self, writer: StreamWriter) -> float | None:
        return self._last_seen.get(writer)

    def record_message(self) -> None:
        self._messages_total += 1

    def add_history(self, packet: MessagePacket) -> None:
        self._history.append(
            HistoryItem(
                sender=packet.sender,
                content=packet.content,
                is_action=packet.is_action,
                timestamp=packet.timestamp,
            )
        )
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit :]

    def history_snapshot(self) -> list[HistoryItem]:
        return list(self._history)

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
