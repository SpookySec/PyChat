# PyChat Presentation (Under 10 Minutes)

## Slide 1 - Title (0:30)
**PyChat: Async Terminal Chatroom**
- Python 3.11, asyncio, Textual, Pydantic
- Real-time chat with a clean terminal UI

## Slide 2 - Problem & Goals (0:45)
- Need a fast, lightweight chat for terminals
- Must stay responsive under multiple users
- Simple protocol, easy to test, easy to extend

## Slide 3 - Architecture (1:15)
- Async TCP server using `asyncio.start_server`
- Textual UI client + headless CLI client
- JSON line protocol with strict schema validation

## Slide 4 - Protocol (1:00)
- Pydantic models for CONNECT, MESSAGE, USER_LIST, etc.
- Newline-delimited JSON for streaming safety
- Validation prevents malformed packets

## Slide 5 - Server Flow (1:15)
- Connect -> ACK -> broadcast join
- Message -> store history -> broadcast
- Nick changes -> update mappings -> broadcast
- Heartbeat pings to detect dead sockets

## Slide 6 - Client UI (1:15)
- RichLog with timestamps, markdown rendering
- Typing indicator + user list with online/offline
- Input always focused for fast typing

## Slide 7 - Demo / Showcase (1:30)
- Start server
- Join 2 clients (UI + headless)
- Send messages, /me, /nick, typing indicator
- Show offline users greyed out

## Slide 8 - Performance & Reliability (0:45)
- Async I/O avoids threads and blocking
- Robust handling of disconnects
- History on connect improves usability

## Slide 9 - Future Ideas (0:45)
- Channels, DMs, message persistence
- Access control and moderation

## Slide 10 - Q&A (0:30)

---

# Appendix - Code (Attach in PDF)

Below: paste the full source code for the project files as required.

- shared/protocol.py
- shared/exceptions.py
- server/main.py
- server/daemon.py
- server/state.py
- server/heartbeat.py
- client/main.py
- client/network/node.py
- client/ui/app.py
- client/ui/styles.tcss

(Place code here in the final PDF export.)
