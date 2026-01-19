import asyncio
from typing import Any

from meshcore import EventType, MeshCore
from meshcore.events import Event
from textual.app import App

from .messages import (
    ChannelListUpdated,
    ConnectionStatus,
    ContactListUpdated,
    NewMessage,
)


class MeshClient:
    def __init__(self, app: App, mc: MeshCore):
        self.app = app
        self.mc = mc

    async def start_subscriptions(self):
        """Subscribe to MeshCore events."""
        self.mc.subscribe(EventType.CONTACT_MSG_RECV, self._handle_contact_msg)
        self.mc.subscribe(EventType.CHANNEL_MSG_RECV, self._handle_channel_msg)
        self.mc.subscribe(EventType.CONTACTS, self._handle_contacts_update)
        self.mc.subscribe(EventType.NEW_CONTACT, self._handle_new_contact)
        self.mc.subscribe(EventType.CONNECTED, self._handle_connected)
        self.mc.subscribe(EventType.DISCONNECTED, self._handle_disconnected)

        # Also subscribe to channels update if available or poll for it
        # Based on CLI, channels are fetched via get_channels
        await self.mc.start_auto_message_fetching()

    async def _handle_contact_msg(self, event: Event):
        msg = event.payload
        # Normalize data structure if needed, or pass raw
        # Based on CLI, payload has 'text', 'sender', etc.
        # We might need to enrich it with sender name if it's just a key

        # Basic enrichment
        if "pubkey_prefix" in msg:
            contact = self.mc.get_contact_by_key_prefix(msg["pubkey_prefix"])
            if contact:
                msg["sender_name"] = contact.get("adv_name", "Unknown")
            else:
                msg["sender_name"] = msg["pubkey_prefix"][:8]

        msg["context_type"] = "contact"  # Explicitly mark as direct message
        self.app.post_message(NewMessage(msg))

    async def _handle_channel_msg(self, event: Event):
        msg = event.payload
        # Enrich with channel name
        if "channel_idx" in msg and hasattr(self.mc, "channels") and self.mc.channels:
            if msg["channel_idx"] < len(self.mc.channels):
                msg["channel_name"] = self.mc.channels[msg["channel_idx"]].get(
                    "channel_name"
                )

        msg["context_type"] = "channel"
        self.app.post_message(NewMessage(msg))

    async def _handle_contacts_update(self, event: Event):
        self.app.post_message(ContactListUpdated(event.payload))

    async def _handle_new_contact(self, event: Event):
        # Trigger a full contact refresh or just add one
        # For now, let's just trigger a status update or similar.
        # Actually, let's just re-fetch or pass the new contact
        # The app might want to refresh the list.
        # But wait, CONTACTS event usually follows getting contacts.
        pass

    async def _handle_connected(self, event: Event):
        self.app.post_message(ConnectionStatus("Connected", True))

    async def _handle_disconnected(self, event: Event):
        self.app.post_message(ConnectionStatus("Disconnected", False))

    async def fetch_initial_data(self):
        """Fetch contacts and channels on startup."""
        await self.mc.commands.get_contacts_async()

        # Fetch channels - this logic is from CLI get_channels
        channels = []
        ch = 0
        while True:
            res = await self.mc.commands.get_channel(ch)
            if res.type == EventType.ERROR:
                break
            info = res.payload
            channels.append(info)
            ch += 1

        # We can store channels in mc or just post them
        self.mc.channels = channels  # Store like CLI does
        self.app.post_message(ChannelListUpdated(channels))

        # Sync unread messages
        await self.sync_messages()

    async def sync_messages(self):
        """Fetch all pending messages from the device."""
        while True:
            res = await self.mc.commands.get_msg()
            if res.type == EventType.NO_MORE_MSGS or res.type == EventType.ERROR:
                break
            
            # Dispatch based on type
            if res.type == EventType.CONTACT_MSG_RECV:
                await self._handle_contact_msg(res)
            elif res.type == EventType.CHANNEL_MSG_RECV:
                await self._handle_channel_msg(res)
