from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import Label, Input, Button
from textual.containers import Grid, Vertical

class SettingsScreen(ModalScreen):
    DEFAULT_CSS = """
    SettingsScreen {
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

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Settings", id="title"),
            Label("Device Name:"),
            Input(placeholder="Enter name", id="name_input"),
            Label("TX Power (dBm):"),
            Input(placeholder="e.g. 22", id="tx_input", type="integer"),
            Vertical(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", id="cancel"),
                id="buttons"
            ),
            id="dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            name = self.query_one("#name_input", Input).value
            tx = self.query_one("#tx_input", Input).value
            self.dismiss({"name": name, "tx": tx})
        else:
            self.dismiss()
