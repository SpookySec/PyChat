from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, ListItem, ListView, RichLog, Static

from shared.protocol import (
    ConnectAckPacket,
    MessagePacket,
    UserJoinedPacket,
    UserLeftPacket,
)

from ..network.node import ChatClient


@dataclass
class ChatLine:
    text: str
    style: str | None = None


class ChatEvent(Message):
    def __init__(self, line: ChatLine) -> None:
        super().__init__()
        self.line = line


class UserListEvent(Message):
    def __init__(self, users: list[str]) -> None:
        super().__init__()
        self.users = users


class ConnectFailed(Message):
    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason


class ChatApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "Term-Chat"

    def __init__(self, host: str, port: int, username: str) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._username = username
        self._client = ChatClient(self._on_packet)
        self._users: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="layout"):
            with Vertical(id="main"):
                yield RichLog(id="chat-log", highlight=False)
                yield Input(
                    id="chat-input",
                    placeholder="Type a message and press Enter",
                )
            with Vertical(id="sidebar"):
                yield Static("Online", id="sidebar-title")
                yield ListView(id="user-list")

    async def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()
        self._append_line(
            "Connecting...",
            "status-info",
        )
        self.run_worker(self.start_network(), exclusive=True, group="network")

    async def on_shutdown(self) -> None:
        await self._client.close()

    async def start_network(self) -> None:
        try:
            await self._client.connect(
                self._host, self._port, self._username
            )
            await self._client.start_listening()
        except Exception as exc:
            self.post_message(ConnectFailed(str(exc)))

    async def _on_packet(self, packet) -> None:
        if isinstance(packet, ConnectAckPacket):
            if not packet.success:
                self.post_message(ConnectFailed(packet.message))
                return
            self._users = packet.users
            self.post_message(UserListEvent(packet.users))
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"Connected as {self._username}",
                        "status-good",
                    )
                )
            )
            return
        if isinstance(packet, MessagePacket):
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"{packet.sender}: {packet.content}",
                        "status-info",
                    )
                )
            )
        elif isinstance(packet, UserJoinedPacket):
            if packet.username not in self._users:
                self._users.append(packet.username)
                self._users.sort()
                self.post_message(UserListEvent(self._users))
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"* {packet.username} joined",
                        "status-good",
                    )
                )
            )
        elif isinstance(packet, UserLeftPacket):
            if packet.username in self._users:
                self._users.remove(packet.username)
                self.post_message(UserListEvent(self._users))
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"* {packet.username} left",
                        "status-warn",
                    )
                )
            )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.value = ""
        if not message:
            return
        if message in {"/quit", "/exit"}:
            await self._client.close()
            self.exit()
            return
        await self._client.send_packet(
            MessagePacket(sender=self._username, content=message)
        )

    async def on_chat_event(self, event: ChatEvent) -> None:
        self._append_line(event.line.text, event.line.style)

    async def on_user_list_event(self, event: UserListEvent) -> None:
        list_view = self.query_one("#user-list", ListView)
        list_view.clear()
        for name in event.users:
            list_view.append(ListItem(Static(name)))

    async def on_connect_failed(self, event: ConnectFailed) -> None:
        self._append_line(f"Connection failed: {event.reason}", "status-warn")
        await asyncio.sleep(0.5)
        self.exit()

    def _append_line(self, message: str, style: str | None = None) -> None:
        log = self.query_one("#chat-log", RichLog)
        text = Text(message)
        if style:
            text.stylize(style)
        log.write(text)
