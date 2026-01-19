import asyncio
import json
import time
import sqlite3

from meshcore import MeshCore
from textual.app import App, ComposeResult
from textual.command import Provider
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Static

from .client import MeshClient
from .messages import (
    ChannelListUpdated,
    ConnectionStatus,
    ContactListUpdated,
    NewMessage,
)
from .screens.channel import ChannelScreen
from .screens.settings import SettingsScreen
from .screens.confirmation import ConfirmationScreen
from .widgets.message_log import MessageLog
from .widgets.message_log import MessageLog
from .widgets.sidebar import ContactItem, Sidebar, SidebarHeader
from .widgets.tabbar import TabBar


class MessageInput(Input):
    BINDINGS = [
        ("ctrl+w", "app.close_tab", "Close Tab"),
    ]

class MeshrcApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }

    #main_content {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }

    #message_container {
        height: 1fr;
        border: solid $secondary;
    }

    Input {
        dock: bottom;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+o", "settings", "Settings"),
        ("ctrl+a", "add_channel", "Add Ch"),
        ("ctrl+e", "edit_channel", "Edit Ch"),
        ("delete", "delete_channel", "Delete Ch"),
        ("ctrl+f", "toggle_favorite", "Toggle Fav"),
        ("ctrl+s", "focus_search", "Search Contacts"),
        ("ctrl+n", "next_buffer", "Next"),
        ("ctrl+p", "prev_buffer", "Prev"),
        ("alt+a", "next_active", "Next Active"),
        ("ctrl+w", "close_tab", "Close Tab"),
    ]

    def __init__(self, connection_args, **kwargs):
        super().__init__(**kwargs)
        self.connection_args = connection_args
        self.mc = None
        self.client = None
        self.active_recipient = None  # Can be channel idx (int) or contact pubkey (str)
        self.active_recipient_type = None  # 'channel' or 'contact'
        self.message_history = {}  # Key: recipient_id, Value: list of messages

    def compose(self) -> ComposeResult:
        yield Sidebar()
        with Vertical(id="main_content"):
            yield TabBar(id="main_tabbar")
            with Vertical(id="message_container"):
                yield MessageLog()
            yield Input(placeholder="Type a message...", id="message_input")
        yield Footer()

    def get_system_commands(self, screen):
        for cmd in super().get_system_commands(screen):
            if cmd.title in ("Maximize", "Screenshot", "Grab screenshot"):
                continue
            yield cmd


    async def on_mount(self) -> None:
        self.title = "MeshRC"

        # Initialize MeshCore based on args
        try:
            if self.connection_args["type"] == "serial":
                self.mc = await MeshCore.create_serial(
                    port=self.connection_args["port"],
                    baudrate=self.connection_args.get("baudrate", 115200),
                )
            elif self.connection_args["type"] == "tcp":
                self.mc = await MeshCore.create_tcp(
                    host=self.connection_args["host"], port=self.connection_args["port"]
                )
            elif self.connection_args["type"] == "ble":
                self.mc = await MeshCore.create_ble(
                    address=self.connection_args.get("address")
                )
            else:
                self.notify("Unknown connection type", severity="error")
                return

            self.client = MeshClient(self, self.mc)
            await self.client.start_subscriptions()
            await self.client.fetch_initial_data()

            self.notify("Connected to MeshCore")

        except Exception as e:
            self.notify(f"Connection failed: {e}", severity="error")
            # In a real app, might want to show an error screen

    async def action_toggle_favorite(self):
        if self.active_recipient_type == "contact" and self.active_recipient:
            item_id = f"contact_{self.active_recipient}"
            await self.query_one(Sidebar).toggle_favorite(item_id)
            self.notify("Toggled favorite")

    def action_focus_search(self):
        self.query_one("#contact_search").focus()

    def action_next_buffer(self):
        item = self.query_one(Sidebar).select_next()
        if item:
            self._activate_item(item)

    def action_prev_buffer(self):
        item = self.query_one(Sidebar).select_previous()
        if item:
            self._activate_item(item)

    def action_next_active(self):
        item = self.query_one(Sidebar).select_next_unread()
        if item:
            self._activate_item(item)

    def _activate_item(self, item):
        self._switch_context(item.id)
        if item.id and item.id.startswith("contact_"):
            key = item.id.split("contact_")[1]
            asyncio.create_task(self.query_one(Sidebar).mark_recent(key))

    def on_sidebar_header_add_channel(self, message: SidebarHeader.AddChannel) -> None:
        self.action_add_channel()

    def on_sidebar_header_delete_channel(self, message: SidebarHeader.DeleteChannel) -> None:
        self.action_delete_channel()

    def on_tab_bar_tab_selected(self, message: TabBar.TabSelected):
         self._switch_context(message.tab_id)

    def on_tab_bar_tab_closed(self, message: TabBar.TabClosed):
         self._close_tab(message.tab_id)

    def action_close_tab(self):
        tab_id = self._get_active_id()
        if tab_id:
            self._close_tab(tab_id)

    def _close_tab(self, tab_id):
        # Remove from tab bar
        tab_bar = self.query_one("#main_tabbar", TabBar)
        tab_bar.remove_tab(tab_id)
        
        # If it was active, switch to another or clear
        if self._get_active_id() == tab_id:
            # Simple heuristic: switch to first remaining tab, or clear
            # Or ask sidebar to select next?
            # For now, clear.
            self.active_recipient = None
            self.active_recipient_type = None
            self.query_one(MessageLog).clear()
            # Try to activate another tab if available
            # ... (omitted for brevity, could rely on defaults)

    def action_add_channel(self):
        def handle_add(data):
            if data and data.get("action") == "save" and data.get("name"):
                asyncio.create_task(self._add_channel(data["name"], data.get("key")))

        self.push_screen(ChannelScreen(), handle_add)

    async def _add_channel(self, name, key=None):
        # Find next available index or use standard add command if available
        # Assuming simple set_channel on next available slot for now, or just slot 0 if empty
        # Real MeshCore logic might be more complex

        # Simplistic logic: find first gap or append
        idx = 0
        if hasattr(self.mc, "channels") and self.mc.channels:
            # This logic assumes channels are a list of dicts.
            # We need to find a free index or just use len() if they are sequential
            # But usually max channels is 8 or similar.
            # Let's try to set on the next index = len(channels)
            idx = len(self.mc.channels)

        try:
            # mc.commands.set_channel(index, name, key)
            if key:
                await self.mc.commands.set_channel(idx, name, key)
            else:
                await self.mc.commands.set_channel(idx, name)
            
            self.notify(f"Added channel {name}")
            # Refresh channels
            await self.client.fetch_initial_data()
        except Exception as e:
            self.notify(f"Failed to add channel: {e}", severity="error")

    def action_edit_channel(self):
        if self.active_recipient_type != "channel" or self.active_recipient is None:
            self.notify("Select a channel to edit", severity="warning")
            return

        # Get current name
        current_name = ""
        if hasattr(self.mc, "channels"):
            for ch in self.mc.channels:
                if ch.get("channel_idx") == self.active_recipient:
                    current_name = ch.get("channel_name", "")
                    break

        def handle_edit(data):
            if not data:
                return
            if data.get("action") == "save" and data.get("name"):
                asyncio.create_task(self._edit_channel(data["idx"], data["name"], data.get("key")))
            elif data.get("action") == "delete":
                asyncio.create_task(self._delete_channel(data["idx"]))

        self.push_screen(
            ChannelScreen(channel_idx=self.active_recipient, name=current_name),
            handle_edit,
        )

    async def _edit_channel(self, idx, name, key=None):
        try:
            if key:
                await self.mc.commands.set_channel(idx, name, key)
            else:
                await self.mc.commands.set_channel(idx, name)
            
            self.notify(f"Updated channel {idx} to {name}")
            await self.client.fetch_initial_data()
        except Exception as e:
            self.notify(f"Failed to edit channel: {e}", severity="error")

    async def action_delete_channel(self):
        if self.active_recipient_type != "channel" or self.active_recipient is None:
            self.notify("Select a channel to delete", severity="warning")
            return

        def handle_confirm(confirm):
            if confirm:
                asyncio.create_task(self._delete_channel(self.active_recipient))

        self.push_screen(
            ConfirmationScreen(f"Are you sure you want to delete channel {self.active_recipient}?"),
            handle_confirm
        )

    async def _delete_channel(self, idx):
        try:
            # Assuming empty name deletes/disables it
            await self.mc.commands.set_channel(idx, "")
            self.notify(f"Deleted channel {idx}")
            await self.client.fetch_initial_data()
        except Exception as e:
            self.notify(f"Failed to delete channel: {e}", severity="error")

    async def on_new_message(self, message: NewMessage) -> None:
        msg = message.message_data

        # Log raw message data if logging enabled
        self._log_message(msg)

        # Sender is implicit from context or embedded in text (for channels)
        sender = None

        content = msg.get("text", "")
        timestamp = msg.get("sender_timestamp") or msg.get("timestamp")

        # Determine context (channel or private)
        context_id = None
        if msg.get("context_type") == "channel":
            context_id = f"chan_{msg.get('channel_idx')}"
        else:
            # For private messages, context is the sender's pubkey
            # Or if we sent it, the recipient.
            # Assuming incoming for now.
            context_id = f"contact_{msg.get('pubkey_prefix')}"  # This is partial, usually handled better
            # If we don't have the full key, we might have issues.
            # But the sidebar uses IDs.

        # Store in history
        if context_id not in self.message_history:
            self.message_history[context_id] = []
        self.message_history[context_id].append(msg)

        # If active, display
        current_active_id = self._get_active_id()
        if current_active_id == context_id:
            self.query_one(MessageLog).add_message(sender, content, timestamp)
        current_active_id = self._get_active_id()
        if current_active_id == context_id:
            self.query_one(MessageLog).add_message(sender, content, timestamp)
        else:
            # Increment badge on sidebar AND tab
            self.query_one(Sidebar).increment_unread(context_id)
            count = self.query_one(Sidebar).unread_counts.get(context_id, 0)
            self.query_one("#main_tabbar", TabBar).set_unread(context_id, count)

    def _log_message(self, msg_data: dict):
        log_file = self.connection_args.get("log_file")
        log_db = self.connection_args.get("log_db")
        
        if not log_file and not log_db:
            return

        try:
            # Create a copy to modify for logging without affecting app logic
            log_entry = msg_data.copy()

            # Ensure timestamp exists
            if "timestamp" not in log_entry:
                log_entry["timestamp"] = int(time.time())

            # Emulate meshcore-cli logic for 'name' and 'sender'
            # meshcore-cli adds 'name' and 'sender' based on contact/channel info
            if "name" not in log_entry:
                if "channel_name" in log_entry:
                    log_entry["name"] = log_entry["channel_name"]
                    log_entry["sender"] = log_entry["channel_name"]
                elif "sender_name" in log_entry:
                    log_entry["name"] = log_entry["sender_name"]
                    log_entry["sender"] = log_entry["sender_name"]
                # Fallbacks if my enrichment failed or differed
                elif log_entry.get("type") == "CHAN":
                    log_entry["sender"] = f"channel {log_entry.get('channel_idx')}"
                    log_entry["name"] = log_entry["sender"]
                elif log_entry.get("type") == "PRIV":
                    # pubkey prefix usually
                    prefix = log_entry.get("pubkey_prefix", "unknown")
                    log_entry["sender"] = prefix
                    log_entry["name"] = prefix

            # Remove internal keys to match meshcore-cli format more closely
            for key in ["context_type", "sender_name", "channel_name"]:
                if key in log_entry:
                    del log_entry[key]

            # Write to JSON File
            if log_file:
                with open(log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            
            # Write to SQLite DB
            if log_db:
                self._write_log_db(log_db, log_entry)

        except Exception as e:
            self.notify(f"Logging failed: {e}", severity="error")

    def _write_log_db(self, db_path, log_entry):
        try:
            with sqlite3.connect(db_path) as conn:
                # Prepare data
                # Schema: timestamp, sender, name, text, type, channel_idx, pubkey_prefix, raw_json
                timestamp = log_entry.get("timestamp")
                sender = log_entry.get("sender")
                name = log_entry.get("name")
                text = log_entry.get("text")
                msg_type = log_entry.get("type")
                channel_idx = log_entry.get("channel_idx")
                pubkey_prefix = log_entry.get("pubkey_prefix")
                raw_json = json.dumps(log_entry)
                
                conn.execute(
                    "INSERT INTO msgs (timestamp, sender, name, text, type, channel_idx, pubkey_prefix, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (timestamp, sender, name, text, msg_type, channel_idx, pubkey_prefix, raw_json)
                )
        except Exception as e:
            self.notify(f"DB Logging failed: {e}", severity="error")



    def _get_active_id(self):
        if self.active_recipient is None:
            return None
        if self.active_recipient_type == "channel":
            return f"chan_{self.active_recipient}"
        else:
            return f"contact_{self.active_recipient}"

    async def on_contact_list_updated(self, message: ContactListUpdated) -> None:
        await self.query_one(Sidebar).update_contacts(message.contacts)

    async def on_channel_list_updated(self, message: ChannelListUpdated) -> None:
        self.query_one(Sidebar).update_channels(message.channels)

    async def on_list_view_selected(self, event) -> None:
        item = event.item
        if isinstance(item, ContactItem):
            item_id = item.id
            self._switch_context(item_id)
            
            if item_id and item_id.startswith("contact_"):
                key = item_id.split("contact_")[1]
                sidebar = self.query_one(Sidebar)
                await sidebar.mark_recent(key)


    def on_button_pressed(self, event: Button.Pressed) -> None:
        # if event.button.id == "add_channel_btn":
        #    self.action_add_channel()
        pass

    def _switch_context(self, item_id: str):
        if not item_id:
            return

        # Sync Sidebar Selection
        self.query_one(Sidebar).select_item(item_id)

        # Clear unread
        self.query_one(Sidebar).clear_unread(item_id)
        self.query_one("#main_tabbar", TabBar).set_unread(item_id, 0)

        # Parse ID
        if item_id.startswith("chan_"):
            self.active_recipient_type = "channel"
            self.active_recipient = int(item_id.split("_")[1])
        elif item_id.startswith("contact_"):
            self.active_recipient_type = "contact"
            self.active_recipient = item_id.split("_")[1]

        # Update TabBar
        name = item_id # Fallback
        
        # Get decent name
        if self.active_recipient_type == "channel":
             if hasattr(self.mc, "channels"):
                 for ch in self.mc.channels:
                      if ch.get("channel_idx") == self.active_recipient:
                           name = ch.get("channel_name", str(self.active_recipient))
                           break
        elif self.active_recipient_type == "contact":
             contact = self.mc.get_contact_by_key_prefix(self.active_recipient)
             if contact:
                  name = contact.get("adv_name", self.active_recipient[:8])
        
        tab_bar = self.query_one("#main_tabbar", TabBar)
        tab_bar.add_tab(item_id, name)
        tab_bar.activate_tab(item_id)

        # Header removed
        # self.query_one(
        #     Header
        # ).title = f"MeshRC - {self.active_recipient_type}: {self.active_recipient}"  # Improve name display

        # Reload Log
        log = self.query_one(MessageLog)
        log.clear()

        my_name = self.mc.self_info.get("name", "Me")

        if item_id in self.message_history:
            for msg in self.message_history[item_id]:
                # Only show sender if it's us (outgoing)
                display_sender = None
                if msg.get("sender_name") == my_name:
                    display_sender = my_name

                content = msg.get("text", "")
                log.add_message(display_sender, content)

        # Focus input
        self.query_one("#message_input").focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if self.active_recipient is None:
            self.notify("No recipient selected", severity="error")
            return

        event.input.value = ""

        # Handle slash commands
        if text.startswith("/"):
            await self.handle_slash_command(text)
            return

        try:
            if self.active_recipient_type == "channel":
                await self.mc.commands.send_chan_msg(self.active_recipient, text)
            elif self.active_recipient_type == "contact":
                contact = self.mc.get_contact_by_key_prefix(self.active_recipient)
                if contact:
                    await self.mc.commands.send_msg(contact, text)
                else:
                    self.notify("Contact not found locally", severity="error")
                    return

            my_name = self.mc.self_info.get("name", "Me")
            log = self.query_one(MessageLog)
            log.add_message(my_name, text)

            cid = self._get_active_id()
            if cid not in self.message_history:
                self.message_history[cid] = []
            self.message_history[cid].append({"sender_name": my_name, "text": text})

        except Exception as e:
            self.notify(f"Failed to send: {e}", severity="error")

    async def handle_slash_command(self, command_line: str):
        parts = command_line[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        contact = None
        if self.active_recipient_type == "contact":
            contact = self.mc.get_contact_by_key_prefix(self.active_recipient)

        try:
            if cmd == "rs" or cmd == "status":
                if not contact:
                    self.notify("Select a contact/repeater first", severity="warning")
                    return
                await self.mc.commands.send_statusreq(contact)
                self.notify(f"Status request sent to {contact.get('adv_name')}")

            elif cmd == "login":
                if not contact:
                    self.notify("Select a contact first", severity="warning")
                    return
                if not args:
                    self.notify("Usage: /login <password>", severity="warning")
                    return
                await self.mc.commands.send_login(contact, args)
                self.notify(f"Login request sent to {contact.get('adv_name')}")

            elif cmd == "logout":
                if not contact:
                    self.notify("Select a contact first", severity="warning")
                    return
                await self.mc.commands.send_logout(contact)
                self.notify(f"Logout sent to {contact.get('adv_name')}")

            elif cmd == "trace":
                # Assuming simple trace or using active contact as target
                if contact:
                    # If active contact selected, we can use their key or args as path
                    path = args if args else contact.get("public_key", "")[:2]
                    await self.mc.commands.send_trace(path=path)
                    self.notify(f"Trace sent: {path}")
                else:
                    if not args:
                        self.notify("Usage: /trace <path_hex_csv>", severity="warning")
                        return
                    await self.mc.commands.send_trace(path=args)
                    self.notify(f"Trace sent: {args}")
            else:
                self.notify(f"Unknown command: /{cmd}", severity="error")

        except Exception as e:
            self.notify(f"Command failed: {e}", severity="error")

    def action_settings(self) -> None:
        def set_settings(data):
            if data:
                # Apply settings via MeshCore
                asyncio.create_task(self._apply_settings(data))

        self.push_screen(SettingsScreen(), set_settings)

    async def _apply_settings(self, data):
        # Example implementation
        if "name" in data and data["name"]:
            # self.mc.commands.set_name(data['name']) # Hypothetical command
            pass
        self.notify("Settings saved (simulation)")
