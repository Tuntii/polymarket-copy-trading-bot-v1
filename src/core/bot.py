"""
Bot Engine - Main controller that orchestrates all components.
Now with WebSocket support for real-time monitoring.
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional
from dataclasses import dataclass

from src.config import settings
from src.db import db, SignalRecord, TradeRecord
from src.core.monitor import monitor
from src.core.executor import executor
from src.core.risk import risk_manager, RiskMetrics
from src.core.websocket_client import polymarket_ws
from src.logger import log as file_log


@dataclass
class BotStatus:
    """Bot status information."""
    is_active: bool = False
    mode: str = "PAPER"
    uptime_seconds: float = 0.0
    target_wallet: str = ""
    my_wallet: str = ""
    poll_rate_ms: int = 1000
    signals_detected: int = 0
    trades_executed: int = 0
    trades_failed: int = 0
    last_check: Optional[str] = None
    errors: int = 0
    # WebSocket status
    ws_connected: bool = False
    ws_trades_received: int = 0


class BotEngine:
    """
    Main bot controller.
    Manages the lifecycle of monitor, executor, and WebSocket components.
    
    Uses dual-mode operation:
    - WebSocket for real-time trade notifications (primary)
    - HTTP polling as fallback/backup
    """
    
    def __init__(self):
        self.is_active = False
        self._start_time: Optional[datetime] = None
        self._use_websocket = True  # Enable WebSocket by default
        
        # Callbacks for UI updates
        self._on_signal: Optional[Callable] = None
        self._on_trade: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._on_status: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_signal: Optional[Callable] = None,
        on_trade: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_status: Optional[Callable] = None
    ):
        """Set UI callback functions."""
        self._on_signal = on_signal
        self._on_trade = on_trade
        self._on_log = on_log
        self._on_status = on_status
        
        # Create combined log callback that writes to both UI and file
        async def combined_log(level: str, message: str):
            # Write to file
            file_log(level, message)
            # Write to UI
            if on_log:
                await on_log(level, message)
        
        # Wire up callbacks to components
        if on_signal:
            monitor.set_signal_callback(on_signal)
        if on_trade:
            executor.set_trade_callback(on_trade)
        
        # Use combined logger for all components
        executor.set_log_callback(combined_log)
        monitor.set_log_callback(combined_log)
        risk_manager.set_log_callback(combined_log)
        polymarket_ws.set_callbacks(
            on_trade=self._handle_ws_trade,
            on_log=combined_log
        )
    
    async def _handle_ws_trade(self, signal: SignalRecord):
        """Handle real-time trade from WebSocket."""
        # Add to database and process
        exists = await db.signal_exists(signal.tx_hash)
        if not exists:
            await db.insert_signal(signal)
            monitor.signals_detected += 1
            
            if self._on_signal:
                await self._on_signal(signal)
    
    async def start(self):
        """Start the bot."""
        if self.is_active:
            return
        
        # Connect to database
        await db.connect()
        
        self.is_active = True
        self._start_time = datetime.utcnow()
        
        if self._on_log:
            await self._on_log("INFO", "🚀 Bot starting...")
        
        # Start HTTP polling monitor
        await monitor.start()
        
        # WebSocket disabled - HTTP polling is reliable and working
        # WebSocket endpoint returning 404, needs investigation
        # if self._use_websocket and not settings.PAPER_TRADING:
        #     await polymarket_ws.start()
        
        # Start executor
        await executor.start()
        
        if self._on_log:
            mode = "PAPER" if settings.PAPER_TRADING else "LIVE"
            await self._on_log("INFO", f"✅ Bot running - Mode: {mode}")
            await self._on_log("INFO", f"👀 Target: {settings.USER_ADDRESS[:16]}...")
    
    async def stop(self):
        """Stop the bot."""
        if not self.is_active:
            return
        
        self.is_active = False
        
        if self._on_log:
            await self._on_log("INFO", "🛑 Stopping bot...")
        
        # Stop all components
        # await polymarket_ws.stop()  # Disabled
        await monitor.stop()
        await executor.stop()
        await db.close()
        
        if self._on_log:
            await self._on_log("INFO", "🛑 Bot stopped")
    
    async def toggle(self) -> bool:
        """Toggle bot state. Returns new state."""
        if self.is_active:
            await self.stop()
        else:
            await self.start()
        return self.is_active
    
    def get_status(self) -> BotStatus:
        """Get current bot status."""
        uptime = 0.0
        if self._start_time and self.is_active:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()
        
        last_check = None
        if monitor.last_check:
            last_check = monitor.last_check.strftime("%H:%M:%S")
        
        return BotStatus(
            is_active=self.is_active,
            mode="PAPER" if settings.PAPER_TRADING else "LIVE",
            uptime_seconds=uptime,
            target_wallet=settings.USER_ADDRESS or "Not configured",
            my_wallet=settings.PROXY_WALLET or "Paper wallet",
            poll_rate_ms=int(settings.FETCH_INTERVAL * 1000),
            signals_detected=monitor.signals_detected,
            trades_executed=executor.trades_executed,
            trades_failed=executor.trades_failed,
            last_check=last_check,
            errors=monitor.errors,
            ws_connected=polymarket_ws.connected,
            ws_trades_received=polymarket_ws.trades_received
        )
    
    async def get_risk_metrics(self) -> RiskMetrics:
        """Get current risk metrics."""
        return await risk_manager.get_metrics()


# Global bot instance
bot = BotEngine()

