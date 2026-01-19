from datetime import datetime

from rich.table import Table
from rich.text import Text
from textual.widgets import RichLog

MESSAGE_GROUPING_THRESHOLD_SECONDS = 300


class MessageLog(RichLog):
    def __init__(self, **kwargs):
        # wrap=False because we want the Table to handle wrapping at the correct width
        super().__init__(wrap=False, **kwargs)
        self.last_sender = None
        self.last_ts_val = 0

    def clear(self):
        super().clear()
        self.last_sender = None
        self.last_ts_val = 0

    def add_message(self, sender: str, content: str, timestamp: float = None):
        ts_val = timestamp if timestamp else datetime.now().timestamp()
        ts_str = datetime.fromtimestamp(ts_val).strftime("%H:%M")

        # Parse content for "Sender : Message" pattern
        if not sender and ":" in content:
            parsed_sender, sep, parsed_content = content.partition(":")
            parsed_sender = parsed_sender.strip()

            if 0 < len(parsed_sender) <= 32:
                sender = parsed_sender
                content = parsed_content.strip()

        # Logic for hiding repetitive info
        show_ts = True
        show_sender = True

        if self.last_sender == sender and (
            ts_val - self.last_ts_val < MESSAGE_GROUPING_THRESHOLD_SECONDS
        ):
            show_sender = False
            if ts_str == datetime.fromtimestamp(self.last_ts_val).strftime("%H:%M"):
                show_ts = False

        self.last_sender = sender
        self.last_ts_val = ts_val

        # Get actual available width to force correct wrapping
        # Subtract margin for scrollbar/border
        render_width = max((self.size.width or 80) - 2, 30)

        # Create Grid
        table = Table.grid(padding=(0, 1), expand=True)
        table.width = render_width

        table.add_column(style="dim", width=5, no_wrap=True)
        table.add_column(width=10, justify="right", no_wrap=True)
        table.add_column(width=1, justify="center", style="dim")
        table.add_column(ratio=1)

        # Prepare cells
        c_time = ts_str if show_ts else ""

        # Sender
        c_nick = Text()
        if show_sender and sender:
            # Truncate if too long
            display_sender = sender[:10]
            c_nick.append(display_sender, style="bold cyan")

        c_sep = "│"

        c_msg = content

        table.add_row(c_time, c_nick, c_sep, c_msg)

        self.write(table)
