from __future__ import annotations

import asyncio
from asyncio import StreamReader, StreamWriter
from typing import Callable
from shared.protocol import (
    BasePacket,
    ConnectAckPacket,
    ConnectPacket,
    MessagePacket,
    PingPacket,
    PongPacket,
    UserJoinedPacket,
    UserLeftPacket,
    packet_from_json,
)
from .state import ServerState


async def close_writer(writer: StreamWriter) -> None:
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def broadcast_and_cleanup(
    state: ServerState, packet: BasePacket
) -> None:
    dead_writers = await state.broadcast(packet)
    for writer in dead_writers:
        username = state.remove(writer)
        await close_writer(writer)
        if username and not isinstance(packet, UserLeftPacket):
            await state.broadcast(UserLeftPacket(username=username))


async def handle_client(
    reader: StreamReader,
    writer: StreamWriter,
    state: ServerState,
    log: Callable[[str], None],
) -> None:
    username: str | None = None
    peer = writer.get_extra_info("peername")
    try:
        initial_line = await reader.readline()
        if not initial_line:
            return
        try:
            packet = packet_from_json(initial_line.decode().strip())
        except Exception:
            return
        if not isinstance(packet, ConnectPacket):
            await state.send_packet(
                writer,
                ConnectAckPacket(
                    success=False,
                    message="First packet must be CONNECT.",
                ),
            )
            log(f"rejected connection from {peer}")
            return
        if state.username_taken(packet.username):
            await state.send_packet(
                writer,
                ConnectAckPacket(
                    success=False,
                    message="Username already in use.",
                ),
            )
            log(f"name collision '{packet.username}' from {peer}")
            return
        username = packet.username
        state.add(writer, username)
        stats = state.stats_snapshot()
        log(
            "joined"
            f" user={username} peer={peer}"
            f" users={stats['active_users']}"
            f" uptime={stats['uptime']:.1f}s"
        )
        await state.send_packet(
            writer,
            ConnectAckPacket(
                success=True,
                message="ok",
                users=state.users(),
            ),
        )
        await broadcast_and_cleanup(
            state, UserJoinedPacket(username=username)
        )
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                packet = packet_from_json(line.decode().strip())
            except Exception:
                continue
            state.touch(writer)
            if isinstance(packet, MessagePacket):
                content = packet.content.strip()
                if not content:
                    continue
                state.record_message()
                await broadcast_and_cleanup(
                    state,
                    MessagePacket(sender=username, content=content),
                )
            elif isinstance(packet, PongPacket):
                state.touch(writer)
            elif isinstance(packet, PingPacket):
                await state.send_packet(writer, PongPacket())
    finally:
        if username is not None:
            removed = state.remove(writer)
            if removed:
                stats = state.stats_snapshot()
                log(
                    "left"
                    f" user={removed}"
                    f" users={stats['active_users']}"
                    f" uptime={stats['uptime']:.1f}s"
                )
                await broadcast_and_cleanup(
                    state, UserLeftPacket(username=removed)
                )
        await close_writer(writer)


async def run_server(
    host: str,
    port: int,
    state: ServerState,
    log: Callable[[str], None],
) -> asyncio.AbstractServer:
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, state, log), host, port
    )
    return server
