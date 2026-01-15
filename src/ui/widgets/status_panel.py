"""
Status Panel Widget - Shows bot status and connection info.
"""
from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from src.core import BotStatus


class StatusPanel(Static):
    """Displays bot status information."""
    
    DEFAULT_CSS = """
    StatusPanel {
        width: 100%;
        height: auto;
        min-height: 8;
        margin: 0 1;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._status: BotStatus = BotStatus()
    
    def update_status(self, status: BotStatus):
        """Update displayed status."""
        self._status = status
        self.refresh()
    
    def render(self) -> Panel:
        """Render the status panel."""
        status = self._status
        
        # Status indicator
        if status.is_active:
            indicator = Text("● RUNNING", style="bold green")
        else:
            indicator = Text("○ STOPPED", style="bold red")
        
        # Format uptime
        uptime = status.uptime_seconds
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Create info table
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()
        
        # Mode badge
        mode_style = "yellow" if status.mode == "PAPER" else "red bold"
        mode_text = Text(f"[{status.mode}]", style=mode_style)
        
        table.add_row("Status", indicator)
        table.add_row("Mode", mode_text)
        table.add_row("Uptime", uptime_str)
        table.add_row("Target", Text(status.target_wallet[:20] + "..." if len(status.target_wallet) > 20 else status.target_wallet, style="cyan"))
        table.add_row("My Wallet", Text(status.my_wallet[:20] + "..." if len(status.my_wallet) > 20 else status.my_wallet, style="cyan"))
        table.add_row("Poll Rate", f"{status.poll_rate_ms}ms")
        table.add_row("Last Check", status.last_check or "-")
        
        return Panel(
            table,
            title="[bold blue]📊 Bot Status[/]",
            border_style="blue"
        )
