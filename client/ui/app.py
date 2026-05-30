from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime

from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, ListItem, ListView, RichLog, Static

from shared.protocol import (
    ConnectAckPacket,
    MessagePacket,
    NickAckPacket,
    NickPacket,
    TypingPacket,
    UserInfo,
    UserJoinedPacket,
    UserLeftPacket,
    UserListPacket,
    UserRenamedPacket,
)

from ..network.node import ChatClient


@dataclass
class ChatLine:
    text: str
    style: str | None = None
    timestamp: float | None = None
    markdown: bool = False


class ChatEvent(Message):
    def __init__(self, line: ChatLine) -> None:
        super().__init__()
        self.line = line


class UserListEvent(Message):
    def __init__(self, users: list[UserInfo]) -> None:
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
        self._users: list[UserInfo] = []
        self._typing_users: dict[str, float] = {}
        self._typing_sent = False
        self._last_input_at = 0.0
        self._last_typing_sent = 0.0
        self._typing_idle_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="layout"):
            with Vertical(id="main"):
                yield RichLog(id="chat-log", highlight=False)
                yield Static("", id="typing-indicator")
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
            "bright_red",
            time.time(),
        )
        self.run_worker(self.start_network(), exclusive=True, group="network")
        self.set_interval(1.0, self._refresh_typing)

    async def on_key(self, event: events.Key) -> None:
        input_widget = self.query_one("#chat-input", Input)
        if not input_widget.has_focus:
            input_widget.focus()

    async def on_input_changed(self, event: Input.Changed) -> None:
        self._last_input_at = time.time()
        value = event.value.strip()
        if value:
            await self._send_typing(True)
            self._schedule_typing_idle()
        elif self._typing_sent:
            await self._send_typing(False)

    async def on_shutdown(self) -> None:
        if self._typing_sent:
            await self._send_typing(False)
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
            self.post_message(UserListEvent(self._users))
            for entry in packet.history:
                self.post_message(
                    ChatEvent(
                        ChatLine(
                            self._render_message(entry.sender, entry.content, entry.is_action),
                            None,
                            entry.timestamp,
                            markdown=not entry.is_action,
                        )
                    )
                )
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"Connected as {self._username}",
                        "green",
                        time.time(),
                    )
                )
            )
            return
        if isinstance(packet, MessagePacket):
            self.post_message(
                ChatEvent(
                    ChatLine(
                        self._render_message(
                            packet.sender,
                            packet.content,
                            packet.is_action,
                        ),
                        None,
                        packet.timestamp,
                        markdown=not packet.is_action,
                    )
                )
            )
        elif isinstance(packet, TypingPacket):
            if packet.username == self._username:
                return
            if packet.is_typing:
                self._typing_users[packet.username] = packet.timestamp
            else:
                self._typing_users.pop(packet.username, None)
            self._update_typing_indicator()
        elif isinstance(packet, UserListPacket):
            self._users = packet.users
            self.post_message(UserListEvent(self._users))
        elif isinstance(packet, UserJoinedPacket):
            self._typing_users.pop(packet.username, None)
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"* {packet.username} joined",
                        "green",
                        packet.timestamp,
                    )
                )
            )
        elif isinstance(packet, UserLeftPacket):
            self._typing_users.pop(packet.username, None)
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"* {packet.username} left",
                        "red",
                        packet.timestamp,
                    )
                )
            )
        elif isinstance(packet, UserRenamedPacket):
            if packet.old_username == self._username:
                self._username = packet.new_username
            self.post_message(
                ChatEvent(
                    ChatLine(
                        f"* {packet.old_username} is now {packet.new_username}",
                        "bright_red",
                        packet.timestamp,
                    )
                )
            )
        elif isinstance(packet, NickAckPacket):
            style = "green" if packet.success else "red"
            message = packet.message
            if packet.success and packet.new_username:
                self._username = packet.new_username
                message = f"Nickname set to {packet.new_username}"
            self.post_message(
                ChatEvent(
                    ChatLine(
                        message,
                        style,
                        time.time(),
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
        if message.startswith("/nick "):
            new_name = message.split(" ", 1)[1].strip()
            if new_name:
                if self._typing_sent:
                    await self._send_typing(False)
                await self._client.send_packet(NickPacket(new_username=new_name))
            else:
                self._append_line("Nickname cannot be empty", "red", time.time())
            return
        if message.startswith("/me "):
            action = message.split(" ", 1)[1].strip()
            if action:
                if self._typing_sent:
                    await self._send_typing(False)
                await self._client.send_packet(
                    MessagePacket(
                        sender=self._username,
                        content=action,
                        is_action=True,
                    )
                )
            return
        if self._typing_sent:
            await self._send_typing(False)
        await self._client.send_packet(
            MessagePacket(sender=self._username, content=message)
        )

    async def on_chat_event(self, event: ChatEvent) -> None:
        self._append_line(
            event.line.text,
            event.line.style,
            event.line.timestamp,
            event.line.markdown,
        )

    async def on_user_list_event(self, event: UserListEvent) -> None:
        list_view = self.query_one("#user-list", ListView)
        list_view.clear()
        for user in event.users:
            style = "green" if user.online else "grey50"
            label = Text("● ", style=style)
            label.append(user.username, style=style)
            list_view.append(ListItem(Static(label)))

    async def on_connect_failed(self, event: ConnectFailed) -> None:
        self._append_line(
            f"Connection failed: {event.reason}",
            "red",
            time.time(),
        )
        await asyncio.sleep(0.5)
        self.exit()

    def _append_line(
        self,
        message: str,
        style: str | None = None,
        timestamp: float | None = None,
        markdown: bool = False,
    ) -> None:
        log = self.query_one("#chat-log", RichLog)
        stamp = self._format_timestamp(timestamp)
        table = Table.grid(padding=(0, 1))
        table.add_column(width=10, no_wrap=True)
        table.add_column(ratio=1)
        stamp_text = Text(f"[{stamp}]", style="grey50")
        if markdown:
            content = Markdown(message)
        else:
            content = Text(message, style=style or "")
        table.add_row(stamp_text, content)
        log.write(table)

    @staticmethod
    def _format_timestamp(timestamp: float | None) -> str:
        if timestamp is None:
            timestamp = time.time()
        return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

    @staticmethod
    def _render_message(sender: str, content: str, is_action: bool) -> str:
        if is_action:
            return f"* {sender} {content}"
        return f"{sender}: {content}"

    def _schedule_typing_idle(self) -> None:
        if self._typing_idle_task is not None:
            self._typing_idle_task.cancel()
        self._typing_idle_task = asyncio.create_task(self._typing_idle())

    async def _typing_idle(self) -> None:
        try:
            await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            return
        if time.time() - self._last_input_at >= 2.5:
            await self._send_typing(False)

    async def _send_typing(self, is_typing: bool) -> None:
        if not self._client.is_connected:
            return
        now = time.time()
        if is_typing:
            if now - self._last_typing_sent < 1.5:
                return
            self._last_typing_sent = now
        if self._typing_sent == is_typing:
            return
        self._typing_sent = is_typing
        await self._client.send_packet(
            TypingPacket(username=self._username, is_typing=is_typing)
        )

    def _refresh_typing(self) -> None:
        now = time.time()
        expired = [
            name for name, ts in self._typing_users.items() if now - ts > 4.0
        ]
        for name in expired:
            self._typing_users.pop(name, None)
        self._update_typing_indicator()

    def _update_typing_indicator(self) -> None:
        indicator = self.query_one("#typing-indicator", Static)
        names = sorted(self._typing_users.keys(), key=str.lower)
        if not names:
            indicator.update("")
            return
        
        if len(names) == 1:
            label = f"{names[0]} is typing..."
        elif len(names) == 2:
            label = f"{names[0]} and {names[1]} are typing..."
        else:
            label = f"{names[0]}, {names[1]} and {len(names) - 2} others are typing..."
        indicator.update(label)
