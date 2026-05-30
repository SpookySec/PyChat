from __future__ import annotations

import argparse
import asyncio
from typing import Final

from shared.protocol import (
    ConnectAckPacket,
    MessagePacket,
    NickAckPacket,
    NickPacket,
    UserJoinedPacket,
    UserLeftPacket,
    UserListPacket,
    UserRenamedPacket,
)

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .network.node import ChatClient
from .ui.app import ChatApp


async def run_headless(host: str, port: int, username: str) -> None:
    console = Console()
    stop_event = asyncio.Event()
    ack_event = asyncio.Event()
    ack_success = True

    def render_banner() -> None:
        title = Text("Term-Chat", style="bold magenta")
        subtitle = Text(
            f"Headless mode | {username}@{host}:{port}",
            style="cyan",
        )
        body = Text()
        body.append("Commands: ", style="bold")
        body.append("/help ", style="green")
        body.append("/quit ", style="red")
        body.append("/exit", style="red")
        panel = Panel(
            body,
            title=title,
            subtitle=subtitle,
            border_style="magenta",
            box=box.ROUNDED,
        )
        console.print(panel)

    def render_help() -> None:
        help_text = Text()
        help_text.append("/help", style="green")
        help_text.append(" - show this message\n")
        help_text.append("/nick <name>", style="cyan")
        help_text.append(" - change nickname\n")
        help_text.append("/me <action>", style="cyan")
        help_text.append(" - action message\n")
        help_text.append("/quit", style="red")
        help_text.append(" - disconnect and exit\n")
        help_text.append("/exit", style="red")
        help_text.append(" - disconnect and exit\n")
        help_text.append("Anything else sends a chat message.\n", style="cyan")
        console.print(Panel(help_text, title="Help", box=box.SQUARE))

    async def on_packet(packet) -> None:
        nonlocal ack_success, username
        if isinstance(packet, ConnectAckPacket):
            if not packet.success:
                ack_success = False
                console.print(f"[bold red][server][/bold red] {packet.message}")
                stop_event.set()
            else:
                users = ", ".join(
                    user.username for user in packet.users if user.online
                )
                users = users or "(none)"
                console.print(
                    f"[bold green][server][/bold green] connected. users={users}"
                )
                for entry in packet.history:
                    console.print(
                        f"{entry.sender}: {entry.content}"
                    )
                ack_event.set()
            return
        if isinstance(packet, MessagePacket):
            if packet.is_action:
                console.print(
                    f"[bold red]* {packet.sender} {packet.content}[/bold red]"
                )
            else:
                console.print(
                    f"[bold cyan]{packet.sender}[/bold cyan]: {packet.content}"
                )
        elif isinstance(packet, UserJoinedPacket):
            console.print(f"[green]* {packet.username} joined[/green]")
        elif isinstance(packet, UserLeftPacket):
            console.print(f"[yellow]* {packet.username} left[/yellow]")
        elif isinstance(packet, UserListPacket):
            online = ", ".join(
                user.username for user in packet.users if user.online
            )
            console.print(f"[dim]online: {online or '(none)'}[/dim]")
        elif isinstance(packet, UserRenamedPacket):
            console.print(
                f"[magenta]* {packet.old_username} is now {packet.new_username}[/magenta]"
            )
        elif isinstance(packet, NickAckPacket):
            if packet.success and packet.new_username:
                username = packet.new_username
            color = "green" if packet.success else "red"
            console.print(f"[{color}]{packet.message}[/{color}]")

    client = ChatClient(on_packet)
    render_banner()
    await client.connect(host, port, username)
    await client.start_listening()

    await ack_event.wait()
    if not ack_success:
        await client.close()
        return

    quit_tokens: Final = {"/quit", "/exit"}
    while not stop_event.is_set():
        try:
            line = await asyncio.to_thread(input, "")
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break
        message = line.strip()
        if not message:
            continue
        if message == "/help":
            render_help()
            continue
        if message.startswith("/nick "):
            new_name = message.split(" ", 1)[1].strip()
            if new_name:
                await client.send_packet(NickPacket(new_username=new_name))
            continue
        if message.startswith("/me "):
            action = message.split(" ", 1)[1].strip()
            if action:
                await client.send_packet(
                    MessagePacket(
                        sender=username,
                        content=action,
                        is_action=True,
                    )
                )
            continue
        if message in quit_tokens:
            stop_event.set()
            break
        await client.send_packet(MessagePacket(sender=username, content=message))

    await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal chat client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--username", default="guest")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    if args.headless:
        try:
            asyncio.run(run_headless(args.host, args.port, args.username))
        except KeyboardInterrupt:
            return
        return

    ChatApp(args.host, args.port, args.username).run()


if __name__ == "__main__":
    main()
