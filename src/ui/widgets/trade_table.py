"""
Trade Table Widget - Shows recent trades.
"""
from textual.widgets import Static
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from datetime import datetime

from src.db import TradeRecord


class TradeTable(Static):
    """Displays trade history in a table."""
    
    DEFAULT_CSS = """
    TradeTable {
        width: 100%;
        height: auto;
        min-height: 12;
        margin: 0 1;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._trades: list[TradeRecord] = []
        self._max_rows = 10
    
    def add_trade(self, trade: TradeRecord):
        """Add a new trade to the top."""
        self._trades.insert(0, trade)
        if len(self._trades) > self._max_rows:
            self._trades.pop()
        self.refresh()
    
    def set_trades(self, trades: list[TradeRecord]):
        """Set all trades."""
        self._trades = trades[:self._max_rows]
        self.refresh()
    
    def render(self) -> Panel:
        """Render the trade table."""
        table = Table(
            expand=True,
            box=None,
            padding=(0, 1),
            show_header=True,
            header_style="bold cyan"
        )
        
        table.add_column("Time", width=8)
        table.add_column("Market", min_width=20, max_width=50)
        table.add_column("Side", width=4)
        table.add_column("Size", width=8)
        table.add_column("Price", width=6)
        table.add_column("Status", width=10)
        table.add_column("Latency", width=8)
        
        if not self._trades:
            table.add_row(
                "", Text("No trades yet...", style="dim italic"), 
                "", "", "", "", ""
            )
        else:
            for trade in self._trades:
                # Parse timestamp
                try:
                    if isinstance(trade.timestamp, str):
                        dt = datetime.fromisoformat(trade.timestamp.replace("Z", "+00:00"))
                    else:
                        dt = trade.timestamp
                    time_str = dt.strftime("%H:%M:%S")
                except:
                    time_str = trade.timestamp[:8] if trade.timestamp else "-"
                
                # Side styling
                side_style = "green" if trade.side == "BUY" else "red"
                side_text = Text(trade.side, style=side_style)
                
                # Status styling
                if trade.status == "COPIED":
                    status_text = Text("✅ COPIED", style="green")
                elif trade.status == "PENDING":
                    status_text = Text("⏳ PENDING", style="yellow")
                else:
                    status_text = Text("❌ FAILED", style="red")
                
                # Market name (truncated less aggressively)
                market = trade.market_name or trade.market_id
                if len(market) > 48:
                    market = market[:45] + "..."
                
                # Latency
                latency = f"{trade.latency_ms:.0f}ms" if trade.latency_ms else "-"
                
                table.add_row(
                    time_str,
                    market,
                    side_text,
                    f"${trade.size_usdc:.2f}",
                    f"{trade.price:.2f}",
                    status_text,
                    latency
                )
        
        return Panel(
            table,
            title="[bold yellow]📈 Trade History[/]",
            border_style="yellow"
        )
