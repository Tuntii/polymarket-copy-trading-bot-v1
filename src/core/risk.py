"""
Risk Manager - Advanced risk management with real-time monitoring.
Now with real balance fetching from Polymarket API.
"""
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional, Callable
from collections import deque
import asyncio
import httpx

from src.config import settings
from src.db import db


@dataclass
class Position:
    """Represents an open position."""
    market_id: str
    market_name: str
    side: str  # BUY or SELL
    size: float
    entry_price: float
    current_price: float = 0.0
    timestamp: str = ""
    
    @property
    def pnl(self) -> float:
        """Calculate unrealized PnL."""
        if self.side == "BUY":
            return (self.current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - self.current_price) * self.size
    
    @property
    def pnl_percent(self) -> float:
        """Calculate PnL percentage."""
        if self.entry_price == 0:
            return 0
        return (self.pnl / (self.entry_price * self.size)) * 100


@dataclass
class RiskMetrics:
    """Current risk state with enhanced metrics."""
    # Balance
    current_balance: float = 0.0
    available_balance: float = 0.0
    
    # Exposure
    total_exposure: float = 0.0
    max_exposure: float = 0.0
    
    # P&L
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    
    # Limits
    max_position_size: float = 0.0
    daily_loss_limit: float = 0.0
    
    # Activity
    daily_trades: int = 0
    hourly_trades: int = 0
    win_rate: float = 0.0
    
    # Risk Assessment
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    risk_score: int = 0  # 0-100
    
    # Circuit Breaker
    circuit_breaker_active: bool = False
    circuit_breaker_reason: str = ""
    
    @property
    def exposure_percent(self) -> float:
        if self.max_exposure == 0:
            return 0
        return (self.total_exposure / self.max_exposure) * 100


class RiskManager:
    """
    Advanced risk management with:
    - Real-time position tracking
    - Circuit breaker protection
    - Drawdown monitoring
    - Trade frequency limits
    - Dynamic risk scoring
    """
    
    def __init__(self):
        # Balance tracking - Start with $30 for paper trading, fetch real for live
        self.current_balance = 30.0 if settings.PAPER_TRADING else 0.0
        self.starting_balance = self.current_balance
        self._last_balance_fetch: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        
        # Trade history for frequency tracking
        self._trade_times: deque = deque(maxlen=1000)
        self._last_trade_time: datetime = datetime.min
        
        # Circuit breaker state
        self._circuit_breaker_active = False
        self._circuit_breaker_until: Optional[datetime] = None
        self._circuit_breaker_reason = ""
        
        # Callbacks
        self._on_log: Optional[Callable] = None
        
        # Risk metrics cache
        self._daily_high_balance = self.current_balance
        self._daily_low_balance = self.current_balance
        self._max_drawdown = 0.0
    
    def set_log_callback(self, callback: Callable):
        """Set logging callback."""
        self._on_log = callback
    
    async def _log(self, level: str, message: str):
        """Internal logging."""
        if self._on_log:
            await self._on_log(level, message)
    
    async def fetch_balance(self) -> float:
        """
        Fetch real USDC balance from Polygon RPC.
        Updates current_balance and returns it.
        """
        if settings.PAPER_TRADING:
            return self.current_balance
        
        # Rate limit: fetch at most once per 10 seconds
        now = datetime.utcnow()
        if self._last_balance_fetch and (now - self._last_balance_fetch).total_seconds() < 10:
            return self.current_balance
        
        try:
            if not self._http_client:
                self._http_client = httpx.AsyncClient(timeout=10.0)
            
            wallet = settings.PROXY_WALLET or settings.USER_ADDRESS
            
            # Prepare JSON-RPC call for balanceOf(address)
            # Function signature hash for balanceOf(address) is 0x70a08231
            clean_addr = wallet[2:] if wallet.startswith("0x") else wallet
            data = "0x70a08231" + clean_addr.zfill(64)
            
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {
                        "to": settings.USDC_CONTRACT_ADDRESS,
                        "data": data
                    },
                    "latest"
                ],
                "id": 1
            }
            
            response = await self._http_client.post(settings.RPC_URL, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    hex_value = result["result"]
                    # USDC has 6 decimals
                    balance = int(hex_value, 16) / 1e6
                    
                    self.current_balance = balance
                    self._last_balance_fetch = now
                    
                    # Update daily high/low
                    if balance > self._daily_high_balance:
                        self._daily_high_balance = balance
                    if balance < self._daily_low_balance:
                        self._daily_low_balance = balance
                    
                    if self.starting_balance == 0:
                        self.starting_balance = balance
                        
                    return balance
                else:
                    await self._log("DEBUG", f"RPC Error: {result}")
            else:
                await self._log("DEBUG", f"RPC HTTP Error: {response.status_code}")
                
        except Exception as e:
            await self._log("DEBUG", f"Could not fetch balance: {e}")
        
        return self.current_balance
    
    async def check_trade(self, amount_usdc: float, market_id: str = "") -> Tuple[bool, str]:
        """
        Validate a trade against all risk rules.
        Returns (allowed, reason).
        """
        # === CIRCUIT BREAKER CHECK ===
        if self._circuit_breaker_active:
            if self._circuit_breaker_until and datetime.utcnow() < self._circuit_breaker_until:
                return False, f"🚨 Circuit breaker active: {self._circuit_breaker_reason}"
            else:
                # Reset circuit breaker
                self._circuit_breaker_active = False
                await self._log("INFO", "✅ Circuit breaker reset")
        
        stats = await db.get_today_stats()
        exposure = await db.get_total_exposure()
        
        # === 1. MINIMUM TRADE AMOUNT ===
        if amount_usdc < settings.MIN_TRADE_AMOUNT_USDC:
            return False, f"Below min trade (${settings.MIN_TRADE_AMOUNT_USDC})"
        
        # === 2. MAXIMUM POSITION SIZE ===
        if amount_usdc > settings.MAX_POSITION_SIZE_USDC:
            return False, f"Exceeds max position (${settings.MAX_POSITION_SIZE_USDC})"
        
        # === 3. TOTAL EXPOSURE LIMIT ===
        new_exposure = exposure + amount_usdc
        if new_exposure > settings.MAX_TOTAL_EXPOSURE_USDC:
            return False, f"Exceeds max exposure (${settings.MAX_TOTAL_EXPOSURE_USDC})"
        
        # === 4. DAILY LOSS LIMIT ===
        daily_pnl = stats.get("total_pnl", 0)
        if daily_pnl < 0 and abs(daily_pnl) >= settings.MAX_DAILY_LOSS_USDC:
            await self._trigger_circuit_breaker("Daily loss limit reached", minutes=60)
            return False, f"Daily loss limit (${settings.MAX_DAILY_LOSS_USDC})"
        
        # === 5. DAILY TRADE LIMIT ===
        if stats.get("successful", 0) >= settings.MAX_TRADES_PER_DAY:
            return False, f"Max daily trades ({settings.MAX_TRADES_PER_DAY})"
        
        # === 6. HOURLY TRADE LIMIT ===
        hourly_trades = self._count_trades_in_last_hour()
        if hourly_trades >= settings.MAX_TRADES_PER_HOUR:
            return False, f"Max hourly trades ({settings.MAX_TRADES_PER_HOUR})"
        
        # === 7. MINIMUM TIME BETWEEN TRADES ===
        elapsed = (datetime.utcnow() - self._last_trade_time).total_seconds() * 1000
        if elapsed < settings.MIN_TIME_BETWEEN_TRADES_MS:
            return False, f"Too soon ({elapsed:.0f}ms < {settings.MIN_TIME_BETWEEN_TRADES_MS}ms)"
        
        # === 8. BALANCE PROTECTION ===
        min_required = settings.MIN_BALANCE_TO_KEEP_USDC + amount_usdc
        if self.current_balance < min_required:
            return False, f"Insufficient balance (need ${min_required:.2f})"
        
        # === 9. MAX BALANCE USAGE ===
        max_usable = self.current_balance * (settings.MAX_BALANCE_USAGE_PERCENT / 100)
        if exposure + amount_usdc > max_usable:
            return False, f"Exceeds {settings.MAX_BALANCE_USAGE_PERCENT}% balance usage"
        
        # === 10. DRAWDOWN CHECK ===
        current_drawdown = self._calculate_drawdown()
        if current_drawdown >= settings.STOP_LOSS_PERCENT:
            await self._trigger_circuit_breaker(f"Drawdown limit ({current_drawdown:.1f}%)", minutes=120)
            return False, f"Drawdown limit reached ({current_drawdown:.1f}%)"
        
        # === ALL CHECKS PASSED ===
        self._last_trade_time = datetime.utcnow()
        self._trade_times.append(datetime.utcnow())
        
        return True, "OK"
    
    def _count_trades_in_last_hour(self) -> int:
        """Count trades in the last hour."""
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        return sum(1 for t in self._trade_times if t > one_hour_ago)
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown from daily high."""
        if self._daily_high_balance == 0:
            return 0
        drawdown = (self._daily_high_balance - self.current_balance) / self._daily_high_balance * 100
        self._max_drawdown = max(self._max_drawdown, drawdown)
        return drawdown
    
    async def _trigger_circuit_breaker(self, reason: str, minutes: int = 30):
        """Activate circuit breaker to halt all trading."""
        self._circuit_breaker_active = True
        self._circuit_breaker_until = datetime.utcnow() + timedelta(minutes=minutes)
        self._circuit_breaker_reason = reason
        
        await self._log("ERROR", f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")
        await self._log("WARNING", f"Trading halted for {minutes} minutes")
    
    async def get_metrics(self) -> RiskMetrics:
        """Get comprehensive risk metrics."""
        # Fetch real balance if in live mode
        if not settings.PAPER_TRADING:
            await self.fetch_balance()
        
        stats = await db.get_today_stats()
        exposure = await db.get_total_exposure()
        
        # Calculate unrealized PnL from positions
        unrealized_pnl = sum(p.pnl for p in self.positions.values())
        
        # Calculate win rate
        total_trades = stats.get("total_trades", 0)
        successful = stats.get("successful", 0)
        win_rate = (successful / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate risk score (0-100)
        risk_score = self._calculate_risk_score(stats, exposure)
        
        # Determine risk level
        if risk_score >= 80 or self._circuit_breaker_active:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return RiskMetrics(
            current_balance=self.current_balance,
            available_balance=self.current_balance - exposure,
            total_exposure=exposure,
            max_exposure=settings.MAX_TOTAL_EXPOSURE_USDC,
            daily_pnl=stats.get("total_pnl", 0),
            unrealized_pnl=unrealized_pnl,
            total_pnl=stats.get("total_pnl", 0) + unrealized_pnl,
            max_position_size=settings.MAX_POSITION_SIZE_USDC,
            daily_loss_limit=settings.MAX_DAILY_LOSS_USDC,
            daily_trades=stats.get("total_trades", 0),
            hourly_trades=self._count_trades_in_last_hour(),
            win_rate=win_rate,
            risk_level=risk_level,
            risk_score=risk_score,
            circuit_breaker_active=self._circuit_breaker_active,
            circuit_breaker_reason=self._circuit_breaker_reason
        )
    
    def _calculate_risk_score(self, stats: dict, exposure: float) -> int:
        """Calculate overall risk score from 0-100."""
        score = 0
        
        # Exposure contribution (0-30 points)
        if settings.MAX_TOTAL_EXPOSURE_USDC > 0:
            exposure_pct = exposure / settings.MAX_TOTAL_EXPOSURE_USDC
            score += min(30, int(exposure_pct * 30))
        
        # Loss contribution (0-30 points)
        daily_pnl = stats.get("total_pnl", 0)
        if daily_pnl < 0 and settings.MAX_DAILY_LOSS_USDC > 0:
            loss_pct = abs(daily_pnl) / settings.MAX_DAILY_LOSS_USDC
            score += min(30, int(loss_pct * 30))
        
        # Drawdown contribution (0-20 points)
        drawdown = self._calculate_drawdown()
        score += min(20, int(drawdown / settings.STOP_LOSS_PERCENT * 20))
        
        # Trade frequency contribution (0-20 points)
        hourly = self._count_trades_in_last_hour()
        if settings.MAX_TRADES_PER_HOUR > 0:
            freq_pct = hourly / settings.MAX_TRADES_PER_HOUR
            score += min(20, int(freq_pct * 20))
        
        return min(100, score)
    
    def update_balance(self, delta: float):
        """Update balance after a trade."""
        self.current_balance += delta
        
        # Track daily high/low
        self._daily_high_balance = max(self._daily_high_balance, self.current_balance)
        self._daily_low_balance = min(self._daily_low_balance, self.current_balance)
    
    def add_position(self, market_id: str, market_name: str, side: str, size: float, price: float):
        """Add or update a position."""
        self.positions[market_id] = Position(
            market_id=market_id,
            market_name=market_name,
            side=side,
            size=size,
            entry_price=price,
            current_price=price,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def update_position_price(self, market_id: str, current_price: float):
        """Update current price for a position."""
        if market_id in self.positions:
            self.positions[market_id].current_price = current_price
    
    def close_position(self, market_id: str) -> Optional[float]:
        """Close a position and return realized PnL."""
        if market_id in self.positions:
            pnl = self.positions[market_id].pnl
            del self.positions[market_id]
            return pnl
        return None
    
    def reset_daily_stats(self):
        """Reset daily tracking (call at day change)."""
        self._daily_high_balance = self.current_balance
        self._daily_low_balance = self.current_balance
        self._max_drawdown = 0.0
        self._trade_times.clear()


# Global risk manager instance
risk_manager = RiskManager()
