from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, TypeAlias, Union

from pydantic import BaseModel, Field, TypeAdapter


class PacketType(str, Enum):
    CONNECT = "CONNECT"
    CONNECT_ACK = "CONNECT_ACK"
    MESSAGE = "MESSAGE"
    USER_JOINED = "USER_JOINED"
    USER_LEFT = "USER_LEFT"
    PING = "PING"
    PONG = "PONG"


class BasePacket(BaseModel):
    type: PacketType

    def to_wire(self) -> str:
        return f"{self.model_dump_json()}\n"


class ConnectPacket(BasePacket):
    type: Literal[PacketType.CONNECT] = PacketType.CONNECT
    username: str = Field(min_length=1, max_length=32)


class ConnectAckPacket(BasePacket):
    type: Literal[PacketType.CONNECT_ACK] = PacketType.CONNECT_ACK
    success: bool
    message: str
    users: list[str] = Field(default_factory=list)


class MessagePacket(BasePacket):
    type: Literal[PacketType.MESSAGE] = PacketType.MESSAGE
    sender: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=500)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class UserJoinedPacket(BasePacket):
    type: Literal[PacketType.USER_JOINED] = PacketType.USER_JOINED
    username: str = Field(min_length=1, max_length=32)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class UserLeftPacket(BasePacket):
    type: Literal[PacketType.USER_LEFT] = PacketType.USER_LEFT
    username: str = Field(min_length=1, max_length=32)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class PingPacket(BasePacket):
    type: Literal[PacketType.PING] = PacketType.PING
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class PongPacket(BasePacket):
    type: Literal[PacketType.PONG] = PacketType.PONG
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


Packet: TypeAlias = Union[
    ConnectPacket,
    ConnectAckPacket,
    MessagePacket,
    UserJoinedPacket,
    UserLeftPacket,
    PingPacket,
    PongPacket,
]

_packet_adapter = TypeAdapter(Packet)


def packet_from_json(data: str) -> Packet:
    return _packet_adapter.validate_json(data)
