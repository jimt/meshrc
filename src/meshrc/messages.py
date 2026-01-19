from typing import Any

from textual.message import Message


class NewMessage(Message):
    """Emitted when a new message is received."""

    def __init__(self, message_data: dict[str, Any]) -> None:
        self.message_data = message_data
        super().__init__()


class ContactListUpdated(Message):
    """Emitted when the contact list is updated."""

    def __init__(self, contacts: dict[str, Any]) -> None:
        self.contacts = contacts
        super().__init__()


class ChannelListUpdated(Message):
    """Emitted when the channel list is updated."""

    def __init__(self, channels: list) -> None:
        self.channels = channels
        super().__init__()


class ConnectionStatus(Message):
    """Emitted when connection status changes."""

    def __init__(self, status: str, connected: bool) -> None:
        self.status = status
        self.connected = connected
        super().__init__()
