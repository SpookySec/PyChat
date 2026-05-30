from __future__ import annotations

import asyncio
from asyncio import StreamReader, StreamWriter
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
) -> None:
    username: str | None = None
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
            return
        if state.username_taken(packet.username):
            await state.send_packet(
                writer,
                ConnectAckPacket(
                    success=False,
                    message="Username already in use.",
                ),
            )
            return
        username = packet.username
        state.add(writer, username)
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
                await broadcast_and_cleanup(
                    state, UserLeftPacket(username=removed)
                )
        await close_writer(writer)


async def run_server(
    host: str, port: int, state: ServerState
) -> asyncio.AbstractServer:
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, state), host, port
    )
    return server
