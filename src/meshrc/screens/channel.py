from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ChannelScreen(ModalScreen):
    DEFAULT_CSS = """
    ChannelScreen {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto;
        padding: 0 1;
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }

    #title {
        column-span: 2;
        height: 1;
        width: 100%;
        content-align: center middle;
        text-style: bold;
    }

    Label {
        height: 3;
        content-align: left middle;
    }

    Input {
        width: 100%;
    }

    #buttons {
        column-span: 2;
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        channel_idx: int = None,
        name: str = "",
        key: str = "",
        psk: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.channel_idx = channel_idx
        self.initial_name = name
        self.initial_key = key  # Private key or similar

    def on_mount(self) -> None:
        self.query_one("#name_input").focus()

    def compose(self) -> ComposeResult:
        title = "Edit Channel" if self.channel_idx is not None else "Add Channel"

        buttons = [
            Button("Save", variant="primary", id="save"),
            Button("Cancel", id="cancel"),
        ]

        if self.channel_idx is not None:
            buttons.insert(1, Button("Delete", variant="error", id="delete"))

        yield Grid(
            Label(title, id="title"),
            Label("Name:"),
            Input(value=self.initial_name, placeholder="Channel Name", id="name_input"),
            # Placeholder for potential key/PSK inputs if needed by MeshCore
            # For now, just name is critical based on Sidebar request
            Vertical(*buttons, id="buttons"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            name = self.query_one("#name_input", Input).value
            self.dismiss({"name": name, "idx": self.channel_idx, "action": "save"})
        elif event.button.id == "delete":
            self.dismiss({"idx": self.channel_idx, "action": "delete"})
        else:
            self.dismiss(None)
