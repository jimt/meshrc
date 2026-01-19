from typing import Any

from textual.app import ComposeResult
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, ListItem, ListView, Static
from textual.message import Message


class ContactItem(ListItem):
    """A list item for a contact or channel with an unread badge."""

    DEFAULT_CSS = """
    ContactItem {
        layout: horizontal;
        height: 1;
        padding: 0 1;
    }

    ContactItem Label.name {
        width: 1fr;
        text-overflow: ellipsis;
        text-wrap: nowrap;
        overflow: hidden;
    }

    ContactItem Label.badge {
        width: auto;
        min-width: 2;
        background: $error;
        color: $text;
        text-align: center;
        padding: 0 1;
        display: none;
    }

    ContactItem.unread Label.badge {
        display: block;
    }

    ContactItem.favorite Label.name {
        color: $accent;
        text-style: bold;
    }

    ContactItem.recent Label.name {
        text-style: italic;
    }

    /* Selection highlight */
    ListView > ContactItem.--highlight {
        background: $secondary;
        color: $background;
    }
    """

    unread_count = reactive(0)
    is_favorite = reactive(False)

    def __init__(self, label: str, id: str = None, favorite: bool = False, key: str = "") -> None:
        super().__init__(id=id)
        self.label_text = label
        self.tooltip = f"{label}\n{key}" if key else label
        self.is_favorite = favorite

    def compose(self) -> ComposeResult:
        display_label = f"★ {self.label_text}" if self.is_favorite else self.label_text
        yield Label(display_label, classes="name")
        yield Label(str(self.unread_count), classes="badge")

    def watch_unread_count(self, count: int) -> None:
        if not self.is_mounted:
            return
        try:
            badge = self.query_one(".badge", Label)
            badge.update(str(count))
            if count > 0:
                self.add_class("unread")
            else:
                self.remove_class("unread")
        except Exception:
            pass

    def watch_is_favorite(self, favorite: bool) -> None:
        if not self.is_mounted:
            return
        try:
            name_label = self.query_one(".name", Label)
            display_label = f"★ {self.label_text}" if favorite else self.label_text
            name_label.update(display_label)
            if favorite:
                self.add_class("favorite")
            else:
                self.remove_class("favorite")
        except Exception:
            pass


class SidebarHeader(ListItem):
    """A non-selectable header item for the unified list."""

    DEFAULT_CSS = """
    SidebarHeader {
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        text-style: bold;
        height: 1;
    }
    SidebarHeader:hover {
        background: $primary-darken-2;
    }
    """

class SidebarHeader(ListItem):
    """A non-selectable header item for the unified list."""

    DEFAULT_CSS = """
    SidebarHeader {
        background: $primary-darken-2;
        color: $text;
        height: auto;
        padding: 0 1; 
    }
    
    SidebarHeader > Horizontal {
        height: 1;
        align: left middle;
    }

    SidebarHeader Label {
        text-style: bold;
        width: 1fr;
    }

    SidebarHeader Button {
        min-width: 3;
        width: auto;
        height: 1;
        background: transparent;
        border: none;
        color: $text-muted;
    }
    SidebarHeader Button:hover {
        color: $text;
        background: $primary;
    }
    """

    class AddChannel(Message):
        pass

    class DeleteChannel(Message):
        pass

    def __init__(self, label: str, show_controls: bool = False) -> None:
        super().__init__(disabled=True)
        self.label = label
        self.show_controls = show_controls

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(self.label)
            if self.show_controls:
                yield Button("-", id="remove_channel_btn", variant="error")
                yield Button("+", id="add_channel_btn", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add_channel_btn":
            self.post_message(self.AddChannel())
        elif event.button.id == "remove_channel_btn":
            self.post_message(self.DeleteChannel())
        event.stop()


class Sidebar(Vertical):
    DEFAULT_CSS = """
    Sidebar {
        width: 25%;
        dock: left;
        background: $surface;
        border-right: vkey $background;
    }

    #sidebar_list {
        height: 1fr;
    }

    #contact_search {
        margin: 0;
        border: none;
        background: $surface-lighten-1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_contacts: dict[str, Any] = {}
        self.all_channels: list[dict[str, Any]] = []
        self.favorites: set[str] = set()
        self.recents: list[str] = []
        self.search_query: str = ""
        self.unread_counts: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search contacts...", id="contact_search")
        yield ListView(id="sidebar_list")

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "contact_search":
            self.search_query = event.value.lower()
            await self.refresh_list()

    def update_channels(self, channels: list[dict[str, Any]]) -> None:
        self.all_channels = channels
        import asyncio

        asyncio.create_task(self.refresh_list())

    async def update_contacts(self, contacts: dict[str, Any]) -> None:
        self.all_contacts = contacts
        await self.refresh_list()

    async def mark_recent(self, key: str):
        pass

    async def refresh_list(self) -> None:
        list_view = self.query_one("#sidebar_list", ListView)

        selected_id = None
        if list_view.index is not None and list_view.index < len(list_view.children):
             selected_item = list_view.children[list_view.index]
             selected_id = selected_item.id

        await list_view.clear()

        # Channels
        await list_view.append(SidebarHeader("CHANNELS", show_controls=True))
        sorted_channels = sorted(self.all_channels, key=lambda x: x.get('channel_idx', 0))
        for ch in sorted_channels:
            name = ch.get("channel_name", "")
            if not name: continue
            idx = ch.get('channel_idx')
            c_id = f"chan_{idx}"
            item = ContactItem(name, id=c_id)
            await list_view.append(item)
            if c_id in self.unread_counts:
                item.unread_count = self.unread_counts[c_id]

        # Contacts
        await list_view.append(SidebarHeader("CONTACTS"))

        all_candidates = []
        for key, contact in self.all_contacts.items():
            name = contact.get("adv_name", key[:8])
            if not self.search_query or self.search_query in name.lower():
                all_candidates.append((key, name))
        
        # Sort: Favorites first (False), then Alpha
        all_candidates.sort(key=lambda x: (x[0] not in self.favorites, x[1].lower()))

        for key, name in all_candidates:
            c_id = f"contact_{key}"
            item = ContactItem(name, id=c_id, favorite=(key in self.favorites), key=key)
            await list_view.append(item)
            if c_id in self.unread_counts:
                item.unread_count = self.unread_counts[c_id]

        # Restore selection
        if selected_id:
            for i, child in enumerate(list_view.children):
                if child.id == selected_id:
                    list_view.index = i
                    break

    async def toggle_favorite(self, item_id: str):
        if not item_id or not item_id.startswith("contact_"):
            return
        key = item_id.split("contact_")[1]
        if key in self.favorites:
            self.favorites.remove(key)
        else:
            self.favorites.add(key)
        await self.refresh_list()

    def set_unread(self, item_id: str, count: int):
        self.unread_counts[item_id] = count
        try:
            item = self.query_one(f"#{item_id}", ContactItem)
            item.unread_count = count
        except:
            pass

    def increment_unread(self, item_id: str):
        count = self.unread_counts.get(item_id, 0) + 1
        self.set_unread(item_id, count)

    def clear_unread(self, item_id: str):
        self.set_unread(item_id, 0)

    def select_next(self):
        list_view = self.query_one("#sidebar_list", ListView)
        if not list_view.children: return None
        
        start_index = list_view.index if list_view.index is not None else -1
        next_index = start_index + 1
        
        while next_index < len(list_view.children):
            item = list_view.children[next_index]
            if isinstance(item, ContactItem):
                list_view.index = next_index
                return item
            next_index += 1
        
        next_index = 0
        while next_index <= start_index:
            item = list_view.children[next_index]
            if isinstance(item, ContactItem):
                list_view.index = next_index
                return item
            next_index += 1
        return None

    def select_previous(self):
        list_view = self.query_one("#sidebar_list", ListView)
        if not list_view.children: return None
            
        start_index = list_view.index if list_view.index is not None else len(list_view.children)
        prev_index = start_index - 1
        
        while prev_index >= 0:
            item = list_view.children[prev_index]
            if isinstance(item, ContactItem):
                list_view.index = prev_index
                return item
            prev_index -= 1
            
        prev_index = len(list_view.children) - 1
        while prev_index >= start_index:
            item = list_view.children[prev_index]
            if isinstance(item, ContactItem):
                list_view.index = prev_index
                return item
            prev_index -= 1
        return None

    def select_item(self, item_id: str):
        list_view = self.query_one("#sidebar_list", ListView)
        for i, child in enumerate(list_view.children):
            if child.id == item_id:
                list_view.index = i
                return

    def select_next_unread(self):
        list_view = self.query_one("#sidebar_list", ListView)
        if not list_view.children: return None
            
        start_index = list_view.index if list_view.index is not None else -1
        
        for i in range(start_index + 1, len(list_view.children)):
            item = list_view.children[i]
            if isinstance(item, ContactItem) and item.unread_count > 0:
                list_view.index = i
                return item
                
        for i in range(0, start_index + 1):
            item = list_view.children[i]
            if isinstance(item, ContactItem) and item.unread_count > 0:
                list_view.index = i
                return item
        return None