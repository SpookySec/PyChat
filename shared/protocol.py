from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, TypeAlias, Union

from pydantic import BaseModel, Field, TypeAdapter


class PacketType(str, Enum):
    CONNECT = "CONNECT"
    CONNECT_ACK = "CONNECT_ACK"
    MESSAGE = "MESSAGE"
    USER_LIST = "USER_LIST"
    USER_JOINED = "USER_JOINED"
    USER_LEFT = "USER_LEFT"
    USER_RENAMED = "USER_RENAMED"
    NICK = "NICK"
    NICK_ACK = "NICK_ACK"
    TYPING = "TYPING"
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
    users: list["UserInfo"] = Field(default_factory=list)
    history: list["HistoryItem"] = Field(default_factory=list)


class UserInfo(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    online: bool


class MessagePacket(BasePacket):
    type: Literal[PacketType.MESSAGE] = PacketType.MESSAGE
    sender: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=500)
    is_action: bool = False
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class HistoryItem(BaseModel):
    sender: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=500)
    is_action: bool = False
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class UserListPacket(BasePacket):
    type: Literal[PacketType.USER_LIST] = PacketType.USER_LIST
    users: list[UserInfo] = Field(default_factory=list)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class UserJoinedPacket(BasePacket):
    type: Literal[PacketType.USER_JOINED] = PacketType.USER_JOINED
    username: str = Field(min_length=1, max_length=32)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class UserLeftPacket(BasePacket):
    type: Literal[PacketType.USER_LEFT] = PacketType.USER_LEFT
    username: str = Field(min_length=1, max_length=32)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class UserRenamedPacket(BasePacket):
    type: Literal[PacketType.USER_RENAMED] = PacketType.USER_RENAMED
    old_username: str = Field(min_length=1, max_length=32)
    new_username: str = Field(min_length=1, max_length=32)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class NickPacket(BasePacket):
    type: Literal[PacketType.NICK] = PacketType.NICK
    new_username: str = Field(min_length=1, max_length=32)


class NickAckPacket(BasePacket):
    type: Literal[PacketType.NICK_ACK] = PacketType.NICK_ACK
    success: bool
    message: str
    new_username: str | None = None


class TypingPacket(BasePacket):
    type: Literal[PacketType.TYPING] = PacketType.TYPING
    username: str = Field(min_length=1, max_length=32)
    is_typing: bool
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
    UserListPacket,
    UserJoinedPacket,
    UserLeftPacket,
    UserRenamedPacket,
    NickPacket,
    NickAckPacket,
    TypingPacket,
    PingPacket,
    PongPacket,
]

ConnectAckPacket.model_rebuild()
UserListPacket.model_rebuild()

_packet_adapter = TypeAdapter(Packet)


def packet_from_json(data: str) -> Packet:
    return _packet_adapter.validate_json(data)
