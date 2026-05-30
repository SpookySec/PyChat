from __future__ import annotations

import argparse
import asyncio
import contextlib

from .daemon import broadcast_and_cleanup, run_server
from .heartbeat import heartbeat_loop
from .state import ServerState


async def _serve(host: str, port: int) -> None:
    state = ServerState()
    server = await run_server(host, port, state)

    async def broadcast(packet):
        await broadcast_and_cleanup(state, packet)

    heartbeat_task = asyncio.create_task(
        heartbeat_loop(state, broadcast)
    )
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Terminal chat server"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(_serve(args.host, args.port))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
