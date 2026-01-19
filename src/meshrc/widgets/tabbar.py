from textual.app import ComposeResult
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, HorizontalScroll
from textual.reactive import reactive
from textual.widgets import Button, Label, Static
from textual.message import Message

class Tab(Static):
    DEFAULT_CSS = """
    Tab {
        width: auto;
        height: 1;
        padding: 0 1; 
        background: $surface-darken-1;
        color: $text-muted;
        border-top: none;
        margin-right: 1;
        layout: horizontal;
    }

    Tab:hover {
        background: $surface;
    }

    Tab.active {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    Tab Label.name {
        margin-right: 1;
    }
    
    Tab Label.badge {
        background: $error;
        color: $text;
        min-width: 2;
        padding: 0 1;
        margin-right: 1;
        display: none;
    }
    
    Tab.unread Label.badge {
        display: block;
    }

    Tab Button.close {
        min-width: 1;
        width: auto;
        height: 1;
        border: none;
        background: transparent;
        color: $text-muted;
        padding: 0;
        opacity: 0%;
    }
    Tab.active Button.close {
        opacity: 100%;
    }
    Tab Button.close:hover {
        color: $error;
    }
    """

    class Selected(Message):
        def __init__(self, tab_id: str):
            self.tab_id = tab_id
            super().__init__()

    class Closed(Message):
        def __init__(self, tab_id: str):
            self.tab_id = tab_id
            super().__init__()

    unread_count = reactive(0)

    def __init__(self, label: str, tab_id: str):
        super().__init__(id=tab_id)
        self.label_text = label
        self.tab_id = tab_id

    def compose(self) -> ComposeResult:
        yield Label(self.label_text, classes="name")
        yield Label("0", classes="badge")
        yield Button("x", classes="close", id=f"close_{self.tab_id}")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.tab_id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.classes and "close" in event.button.classes:
            event.stop()
            if self.has_class("active"):
                self.post_message(self.Closed(self.tab_id))
            else:
                # If inactive, clicking the invisible X should probably just select the tab
                self.post_message(self.Selected(self.tab_id))

    def watch_unread_count(self, count: int):
        try:
            badge = self.query_one(".badge", Label)
            badge.update(str(count))
            if count > 0:
                self.add_class("unread")
            else:
                self.remove_class("unread")
        except:
            pass


class TabBar(Horizontal):
    DEFAULT_CSS = """
    TabBar {
        height: 2;
        dock: top;
        background: $surface-darken-2;
        padding: 0 1;
    }

    #tabs_container {
        width: 1fr;
        height: 2;
    }
    """

    class TabClosed(Message):
        def __init__(self, tab_id: str):
            self.tab_id = tab_id
            super().__init__()

    class TabSelected(Message):
        def __init__(self, tab_id: str):
            self.tab_id = tab_id
            super().__init__()

    def compose(self) -> ComposeResult:
        yield HorizontalScroll(id="tabs_container")

    def add_tab(self, tab_id: str, label: str):
        container = self.query_one("#tabs_container", HorizontalScroll)
        # Check if exists
        try:
            container.query_one(f"#{tab_id}")
            return # Already exists
        except:
            pass
        
        container.mount(Tab(label, tab_id))
        self.call_after_refresh(self.scroll_to_tab, tab_id)

    def remove_tab(self, tab_id: str):
        try:
            container = self.query_one("#tabs_container", HorizontalScroll)
            tab = container.query_one(f"#{tab_id}", Tab)
            tab.remove()
        except:
            pass

    def activate_tab(self, tab_id: str):
        container = self.query_one("#tabs_container", HorizontalScroll)
        for tab in container.query(Tab):
            if tab.id == tab_id:
                tab.add_class("active")
            else:
                tab.remove_class("active")
        self.call_after_refresh(self.scroll_to_tab, tab_id)

    def set_unread(self, tab_id: str, count: int):
        try:
            container = self.query_one("#tabs_container", HorizontalScroll)
            tab = container.query_one(f"#{tab_id}", Tab)
            tab.unread_count = count
        except:
            pass

    def scroll_to_tab(self, tab_id: str):
        try:
            container = self.query_one("#tabs_container", HorizontalScroll)
            tab = container.query_one(f"#{tab_id}", Tab)
            container.scroll_to_widget(tab)
        except:
            pass

    def on_tab_selected(self, message: Tab.Selected):
        message.stop()
        self.post_message(self.TabSelected(message.tab_id))

    def on_tab_closed(self, message: Tab.Closed):
        message.stop()
        self.post_message(self.TabClosed(message.tab_id))
    
    def on_button_pressed(self, event: Button.Pressed):
        pass
