"""
Risk Panel Widget - Shows comprehensive risk metrics and limits.
"""
from textual.widgets import Static
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from src.core import RiskMetrics


class RiskPanel(Static):
    """Displays comprehensive risk metrics and limits."""
    
    DEFAULT_CSS = """
    RiskPanel {
        width: 100%;
        height: auto;
        min-height: 10;
        margin: 0 1;
    }
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._metrics: RiskMetrics = RiskMetrics()
    
    def update_metrics(self, metrics: RiskMetrics):
        """Update displayed metrics."""
        self._metrics = metrics
        self.refresh()
    
    def _get_risk_style(self, level: str) -> str:
        """Get style for risk level."""
        styles = {
            "LOW": "green",
            "MEDIUM": "yellow",
            "HIGH": "orange1",
            "CRITICAL": "red bold blink"
        }
        return styles.get(level, "white")
    
    def _get_risk_emoji(self, level: str) -> str:
        """Get emoji for risk level."""
        emojis = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴"
        }
        return emojis.get(level, "⚪")
    
    def render(self) -> Panel:
        """Render the risk panel."""
        m = self._metrics
        
        # Create metrics table
        table = Table.grid(padding=(0, 1))
        table.add_column(style="dim", width=12)
        table.add_column(width=12)
        table.add_column(style="dim", width=12)
        table.add_column(width=12)
        
        # Risk level with emoji and score
        risk_style = self._get_risk_style(m.risk_level)
        risk_emoji = self._get_risk_emoji(m.risk_level)
        risk_text = Text(f"{risk_emoji} {m.risk_level}", style=risk_style)
        
        # Risk score bar
        score_bar = self._make_score_bar(m.risk_score)
        
        # PnL styling
        daily_pnl_style = "green" if m.daily_pnl >= 0 else "red"
        daily_pnl_sign = "+" if m.daily_pnl >= 0 else ""
        daily_pnl_text = Text(f"{daily_pnl_sign}${m.daily_pnl:.2f}", style=daily_pnl_style)
        
        total_pnl_style = "green" if m.total_pnl >= 0 else "red"
        total_pnl_sign = "+" if m.total_pnl >= 0 else ""
        total_pnl_text = Text(f"{total_pnl_sign}${m.total_pnl:.2f}", style=total_pnl_style)
        
        # Win rate styling
        win_style = "green" if m.win_rate >= 50 else "yellow" if m.win_rate >= 30 else "red"
        win_text = Text(f"{m.win_rate:.0f}%", style=win_style)
        
        # Row 1: Balance & Risk
        table.add_row(
            "Balance", f"${m.current_balance:,.2f}",
            "Risk", risk_text
        )
        
        # Row 2: Available & Score
        table.add_row(
            "Available", f"${m.available_balance:,.2f}",
            "Score", score_bar
        )
        
        # Row 3: Exposure & Max
        table.add_row(
            "Exposure", f"${m.total_exposure:.2f}",
            "Max", f"${m.max_exposure:.2f}"
        )
        
        # Row 4: Daily P/L & Total P/L
        table.add_row(
            "Daily P/L", daily_pnl_text,
            "Total P/L", total_pnl_text
        )
        
        # Row 5: Trades & Win Rate
        table.add_row(
            "Trades", f"{m.daily_trades} / {m.hourly_trades}h",
            "Win Rate", win_text
        )
        
        # Build content
        from rich.console import Group
        
        # Exposure progress bar
        exposure_pct = min(100, m.exposure_percent)
        bar_text = Text()
        bar_text.append("Exposure: ", style="dim")
        bar_text.append(self._make_bar(exposure_pct, 25))
        bar_text.append(f" {exposure_pct:.0f}%", style="dim")
        
        # Circuit breaker warning
        if m.circuit_breaker_active:
            cb_text = Text("\n🚨 CIRCUIT BREAKER: ", style="red bold")
            cb_text.append(m.circuit_breaker_reason, style="red")
            content = Group(table, bar_text, cb_text)
            border_style = "red"
            title = "[bold red]🚨 RISK ALERT[/]"
        else:
            content = Group(table, bar_text)
            border_style = "magenta"
            title = "[bold magenta]⚡ Risk Metrics[/]"
        
        return Panel(
            content,
            title=title,
            border_style=border_style
        )
    
    def _make_bar(self, percent: float, width: int = 25) -> Text:
        """Create a simple progress bar."""
        filled = int((percent / 100) * width)
        empty = width - filled
        
        if percent >= 80:
            style = "red"
        elif percent >= 50:
            style = "yellow"
        else:
            style = "green"
        
        bar = Text()
        bar.append("█" * filled, style=style)
        bar.append("░" * empty, style="dim")
        return bar
    
    def _make_score_bar(self, score: int) -> Text:
        """Create a risk score indicator."""
        text = Text()
        
        if score >= 80:
            style = "red bold"
            emoji = "🔴"
        elif score >= 60:
            style = "orange1"
            emoji = "🟠"
        elif score >= 40:
            style = "yellow"
            emoji = "🟡"
        else:
            style = "green"
            emoji = "🟢"
        
        text.append(f"{emoji} {score}", style=style)
        return text

