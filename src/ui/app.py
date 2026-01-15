"""
Polymarket Copy Trading Bot - Terminal UI Application
Built with Textual for a beautiful terminal experience.
"""
import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual.timer import Timer
from rich.text import Text

from src.config import settings
from src.core import bot, BotStatus, RiskMetrics
from src.db import db, TradeRecord
from src.ui.widgets import StatusPanel, RiskPanel, TradeTable, LogPanel


class TitleBar(Static):
    """Custom title bar with app name and mode."""
    
    DEFAULT_CSS = """
    TitleBar {
        width: 100%;
        height: 3;
        background: $primary-darken-2;
        padding: 1 2;
    }
    """
    
    def render(self) -> Text:
        mode = "PAPER" if settings.PAPER_TRADING else "LIVE"
        mode_style = "yellow bold" if mode == "PAPER" else "red bold"
        
        text = Text()
        text.append("🤖 ", style="bold")
        text.append("POLYMARKET COPY TRADING BOT", style="bold white")
        text.append("  │  ", style="dim")
        text.append(f"[{mode}]", style=mode_style)
        
        return text


class CopyTradingApp(App):
    """Main TUI application."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        width: 100%;
        height: 100%;
        padding: 0;
    }
    
    #top-row {
        width: 100%;
        height: auto;
        max-height: 12;
    }
    
    #status-container {
        width: 1fr;
    }
    
    #risk-container {
        width: 1fr;
    }
    
    #trade-container {
        width: 100%;
        height: 1fr;
        min-height: 14;
    }
    
    #log-container {
        width: 100%;
        height: auto;
        min-height: 12;
    }
    
    Footer {
        background: $primary-darken-1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+s", "toggle_bot", "Start/Stop", priority=True),
        Binding("ctrl+l", "clear_logs", "Clear"),
        Binding("f5", "refresh", "Refresh"),
        Binding("f1", "help", "Help"),
        Binding("space", "toggle_bot", "Start/Stop", show=False),
    ]
    
    TITLE = "Polymarket Copy Trading Bot"
    
    def __init__(self):
        super().__init__()
        self._refresh_timer: Timer = None
        self._status_panel: StatusPanel = None
        self._risk_panel: RiskPanel = None
        self._trade_table: TradeTable = None
        self._log_panel: LogPanel = None
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield TitleBar()
        
        with Container(id="main-container"):
            # Top row: Status and Risk side by side
            with Horizontal(id="top-row"):
                with Container(id="status-container"):
                    yield StatusPanel(id="status")
                with Container(id="risk-container"):
                    yield RiskPanel(id="risk")
            
            # Trade history table
            with Container(id="trade-container"):
                yield TradeTable(id="trades")
            
            # Live logs
            with Container(id="log-container"):
                yield LogPanel(id="logs")
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Called when app is mounted."""
        # Get widget references
        self._status_panel = self.query_one("#status", StatusPanel)
        self._risk_panel = self.query_one("#risk", RiskPanel)
        self._trade_table = self.query_one("#trades", TradeTable)
        self._log_panel = self.query_one("#logs", LogPanel)
        
        # Set up bot callbacks
        bot.set_callbacks(
            on_signal=self._on_signal,
            on_trade=self._on_trade,
            on_log=self._on_log
        )
        
        # Initial log
        mode = "🔴 LIVE" if not settings.PAPER_TRADING else "📝 PAPER"
        self._log_panel.add_log("INFO", f"Application started - Mode: {mode}")
        self._log_panel.add_log("INFO", f"Target: {settings.USER_ADDRESS[:20] if settings.USER_ADDRESS else 'Not configured'}...")
        self._log_panel.add_log("INFO", "Press [CTRL+S] or [SPACE] to start the bot")
        
        # Start refresh timer
        self._refresh_timer = self.set_interval(
            settings.REFRESH_RATE_MS / 1000,
            self._refresh_ui
        )
    
    async def _on_signal(self, signal):
        """Handle new signal from monitor."""
        self._log_panel.add_log("INFO", f"🎯 Signal: {signal.side} {signal.market_name}")
    
    async def _on_trade(self, trade: TradeRecord):
        """Handle new trade from executor."""
        self._trade_table.add_trade(trade)
    
    async def _on_log(self, level: str, message: str):
        """Handle log messages."""
        self._log_panel.add_log(level, message)
    
    async def _refresh_ui(self):
        """Periodic UI refresh."""
        # Update status
        status = bot.get_status()
        self._status_panel.update_status(status)
        
        # Update risk metrics if bot is running
        if bot.is_active:
            try:
                metrics = await bot.get_risk_metrics()
                self._risk_panel.update_metrics(metrics)
            except:
                pass
    
    async def action_toggle_bot(self):
        """Toggle bot start/stop."""
        try:
            new_state = await bot.toggle()
            
            # Load recent trades from DB if starting
            if new_state:
                try:
                    trades = await db.get_recent_trades(10)
                    self._trade_table.set_trades(trades)
                except:
                    pass
            
        except Exception as e:
            self._log_panel.add_log("ERROR", f"Toggle failed: {e}")
    
    async def action_clear_logs(self):
        """Clear log panel."""
        self._log_panel.clear()
        self._log_panel.add_log("INFO", "Logs cleared")
    
    async def action_refresh(self):
        """Force refresh."""
        await self._refresh_ui()
        self._log_panel.add_log("INFO", "UI refreshed")
    
    async def action_help(self):
        """Show help."""
        self._log_panel.add_log("INFO", "─" * 40)
        self._log_panel.add_log("INFO", "Keyboard Shortcuts:")
        self._log_panel.add_log("INFO", "  [CTRL+S] or [SPACE] - Start/Stop bot")
        self._log_panel.add_log("INFO", "  [CTRL+L] - Clear logs")
        self._log_panel.add_log("INFO", "  [F5] - Refresh UI")
        self._log_panel.add_log("INFO", "  [F1] - Show this help")
        self._log_panel.add_log("INFO", "  [CTRL+Q] - Quit application")
        self._log_panel.add_log("INFO", "─" * 40)
    
    async def action_quit(self):
        """Quit application."""
        if bot.is_active:
            await bot.stop()
        self.exit()


def run():
    """Entry point for the application."""
    app = CopyTradingApp()
    app.run()


if __name__ == "__main__":
    run()
