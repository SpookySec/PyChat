from __future__ import annotations

import argparse
import asyncio
import contextlib
import time

from .daemon import broadcast_and_cleanup, run_server
from .heartbeat import heartbeat_loop
from .state import ServerState


def _format_uptime(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


async def _serve(host: str, port: int) -> None:
    state = ServerState()
    started_at = time.monotonic()

    def log(message: str) -> None:
        uptime = _format_uptime(time.monotonic() - started_at)
        print(f"[server {uptime}] {message}")

    server = await run_server(host, port, state, log)

    async def broadcast(packet):
        await broadcast_and_cleanup(state, packet)

    heartbeat_task = asyncio.create_task(heartbeat_loop(state, broadcast))

    async def stats_loop() -> None:
        while True:
            await asyncio.sleep(30)
            stats = state.stats_snapshot()
            log(
                "stats"
                f" users={stats['active_users']}"
                f" connections={stats['connections']}"
                f" disconnects={stats['disconnects']}"
                f" messages={stats['messages']}"
            )

    stats_task = asyncio.create_task(stats_loop())
    log(f"listening on {host}:{port}")
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        heartbeat_task.cancel()
        stats_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        with contextlib.suppress(asyncio.CancelledError):
            await stats_task


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
