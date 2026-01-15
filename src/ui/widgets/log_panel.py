"""
Log Panel Widget - Shows live bot logs.
"""
from textual.widgets import Static
from rich.text import Text
from rich.panel import Panel
from datetime import datetime
from collections import deque


class LogEntry:
    """A single log entry."""
    
    def __init__(self, level: str, message: str, timestamp: datetime = None):
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()
    
    def to_text(self) -> Text:
        """Convert to Rich Text."""
        # Timestamp
        time_str = self.timestamp.strftime("%H:%M:%S")
        
        # Level styling
        level_styles = {
            "DEBUG": "dim",
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "red bold",
            "SUCCESS": "green"
        }
        level_style = level_styles.get(self.level, "white")
        
        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append(f"{self.level:<7} ", style=level_style)
        text.append(self.message)
        
        return text


class LogPanel(Static):
    """Displays live log messages."""
    
    DEFAULT_CSS = """
    LogPanel {
        width: 100%;
        height: auto;
        min-height: 10;
        max-height: 15;
        margin: 0 1;
    }
    """
    
    def __init__(self, max_lines: int = 50, **kwargs):
        super().__init__(**kwargs)
        self._logs: deque[LogEntry] = deque(maxlen=max_lines)
        self._display_lines = 8
    
    def add_log(self, level: str, message: str):
        """Add a new log entry."""
        entry = LogEntry(level, message)
        self._logs.append(entry)
        self.refresh()
    
    def clear(self):
        """Clear all logs."""
        self._logs.clear()
        self.refresh()
    
    def render(self) -> Panel:
        """Render the log panel."""
        text = Text()
        
        if not self._logs:
            text.append("Waiting for logs...", style="dim italic")
        else:
            # Show last N entries
            display_logs = list(self._logs)[-self._display_lines:]
            for i, entry in enumerate(display_logs):
                text.append_text(entry.to_text())
                if i < len(display_logs) - 1:
                    text.append("\n")
        
        return Panel(
            text,
            title="[bold green]📜 Live Logs[/]",
            border_style="green"
        )
