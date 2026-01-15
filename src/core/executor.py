"""
Trade Executor - Executes copy trades with risk validation.
Uses py-clob-client for real Polymarket order execution.
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional

from src.config import settings
from src.db import db, SignalRecord, TradeRecord
from src.core.risk import risk_manager

# Try to import py-clob-client for real trading
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False


class TradeExecutor:
    """
    Processes signals and executes copy trades.
    Handles risk validation and trade recording.
    
    Uses py-clob-client for real order execution on Polymarket.
    """
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_trade: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._clob_client = None
        
        # Stats
        self.trades_executed = 0
        self.trades_failed = 0
    
    def set_trade_callback(self, callback: Callable):
        """Set callback for trade events."""
        self._on_trade = callback
    
    def set_log_callback(self, callback: Callable):
        """Set callback for log messages."""
        self._on_log = callback
    
    async def _log(self, level: str, message: str):
        """Internal logging with callback support."""
        if self._on_log:
            await self._on_log(level, message)
    
    def _init_clob_client(self):
        """Initialize the CLOB client for real trading."""
        if not CLOB_AVAILABLE:
            return False
        
        if not settings.PRIVATE_KEY or not settings.PROXY_WALLET:
            return False
        
        try:
            self._clob_client = ClobClient(
                host=settings.CLOB_HTTP_URL,
                key=settings.PRIVATE_KEY,
                chain_id=137,  # Polygon mainnet
                funder=settings.PROXY_WALLET
            )
            return True
        except Exception as e:
            return False
    
    async def start(self):
        """Start execution loop."""
        if self._running:
            return
        
        self._running = True
        
        # Initialize CLOB client for live trading
        if not settings.PAPER_TRADING:
            if CLOB_AVAILABLE:
                if self._init_clob_client():
                    await self._log("INFO", "✅ CLOB client initialized for LIVE trading")
                else:
                    await self._log("ERROR", "❌ Failed to initialize CLOB client - check credentials")
            else:
                await self._log("WARNING", "⚠️ py-clob-client not installed. Run: pip install py-clob-client")
        
        self._task = asyncio.create_task(self._execution_loop())
        await self._log("INFO", "Trade Executor started")
    
    async def stop(self):
        """Stop execution loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._log("INFO", "Trade Executor stopped")
    
    async def _execution_loop(self):
        """Main execution loop - processes pending signals."""
        while self._running:
            try:
                # Get unprocessed signals
                signals = await db.get_unprocessed_signals()
                
                for signal in signals:
                    await self._execute_signal(signal)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._log("ERROR", f"Execution error: {e}")
            
            await asyncio.sleep(0.1)  # High frequency check
    
    async def _execute_signal(self, signal: SignalRecord):
        """Process a single signal."""
        start_time = datetime.utcnow()
        
        await self._log("INFO", f"Processing: {signal.side} {signal.market_name}")
        
        # Calculate trade size
        if settings.FIXED_TRADE_AMOUNT > 0:
            copy_amount = settings.FIXED_TRADE_AMOUNT
            await self._log("INFO", f"💰 using fixed amount: ${copy_amount:.2f}")
        else:
            amount_usdc = signal.amount * signal.price
            copy_amount = amount_usdc * (settings.COPY_RATIO_PERCENT / 100)
        
        # CLAMP: If amount exceeds max position size, cap it instead of rejecting
        if copy_amount > settings.MAX_POSITION_SIZE_USDC:
            await self._log("WARNING", f"⚠️ Capping trade from ${copy_amount:.2f} to max ${settings.MAX_POSITION_SIZE_USDC:.2f}")
            copy_amount = settings.MAX_POSITION_SIZE_USDC
            
        # CLAMP: Check minimum amount too? (Usually min is hard constraint, but let's check)
        if copy_amount < settings.MIN_TRADE_AMOUNT_USDC:
            # If slightly below, maybe we can bump it up? 
            # Nah, bumping up is riskier. Let's let risk manager handle it or just reject.
            pass
        
        # Risk check
        allowed, reason = await risk_manager.check_trade(copy_amount)
        
        status = "FAILED"
        error_msg = None
        tx_hash = None
        
        if allowed:
            try:
                if settings.PAPER_TRADING:
                    # === PAPER TRADING MODE ===
                    await self._log("INFO", f"📝 PAPER: {signal.side} ${copy_amount:.2f} on {signal.market_name}")
                    await asyncio.sleep(0.1)  # Simulate network delay
                    status = "COPIED"
                    tx_hash = f"paper_{datetime.utcnow().timestamp()}"
                    
                    # Update paper balance
                    if signal.side == "BUY":
                        risk_manager.update_balance(-copy_amount)
                    else:
                        risk_manager.update_balance(copy_amount)
                    
                    self.trades_executed += 1
                else:
                    # === REAL LIVE TRADING ===
                    result = await self._execute_real_trade(signal, copy_amount)
                    
                    if result.get('success'):
                        status = "COPIED"
                        tx_hash = result.get('tx_hash')
                        await self._log("INFO", f"🚀 LIVE: {signal.side} ${copy_amount:.2f} - TX: {tx_hash[:20]}...")
                        self.trades_executed += 1
                    else:
                        status = "FAILED"
                        error_msg = result.get('error', 'Unknown error')
                        await self._log("ERROR", f"Live trade failed: {error_msg}")
                        self.trades_failed += 1
                
            except Exception as e:
                error_msg = str(e)
                await self._log("ERROR", f"Execution failed: {e}")
                self.trades_failed += 1
        else:
            error_msg = reason
            self.trades_failed += 1
            await self._log("WARNING", f"Risk rejected: {reason}")
        
        # Calculate latency
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Record trade
        trade = TradeRecord(
            market_id=signal.market_id,
            market_name=signal.market_name,
            side=signal.side,
            size_usdc=copy_amount,
            price=signal.price,
            status=status,
            error_message=error_msg,
            timestamp=datetime.utcnow().isoformat(),
            tx_hash=tx_hash,
            latency_ms=latency
        )
        
        await db.insert_trade(trade)
        
        # Mark signal as processed
        await db.mark_signal_processed(signal.tx_hash)
        
        # Notify callback
        if self._on_trade:
            await self._on_trade(trade)
        
        # Log result
        emoji = "✅" if status == "COPIED" else "❌"
        await self._log("INFO", f"{emoji} {status}: {signal.side} ${copy_amount:.2f} ({latency:.0f}ms)")
    
    async def _execute_real_trade(self, signal: SignalRecord, amount_usdc: float) -> dict:
        """
        Execute a real trade on Polymarket via CLOB.
        
        Uses py-clob-client to place market orders.
        """
        if not CLOB_AVAILABLE:
            return {
                'success': False,
                'error': 'py-clob-client not installed. Run: pip install py-clob-client'
            }
        
        if not self._clob_client:
            if not self._init_clob_client():
                return {
                    'success': False,
                    'error': 'CLOB client not initialized - check PRIVATE_KEY and PROXY_WALLET'
                }
        
        try:
            # Calculate the number of shares to buy/sell
            # size = amount_usdc / price
            shares = amount_usdc / signal.price if signal.price > 0 else 0
            
            if shares <= 0:
                return {'success': False, 'error': 'Invalid share calculation'}
            
            # Determine order side
            # In Polymarket: BUY = buy YES shares, SELL = sell YES shares (or buy NO)
            side = "BUY" if signal.side == "BUY" else "SELL"
            
            # Apply slippage tolerance
            if side == "BUY":
                # For buys, we're willing to pay slightly more
                limit_price = min(0.99, signal.price * (1 + settings.MAX_SLIPPAGE_PERCENT / 100))
            else:
                # For sells, we accept slightly less
                limit_price = max(0.01, signal.price * (1 - settings.MAX_SLIPPAGE_PERCENT / 100))
            
            # Build the order
            # Note: This is a simplified example - actual implementation may vary
            # based on py-clob-client version and Polymarket API updates
            
            order_args = OrderArgs(
                token_id=signal.market_id,
                price=limit_price,
                size=shares,
                side=side,
                fee_rate_bps=0,  # Polymarket usually has 0 fees
            )
            
            # Place the order (this is synchronous in py-clob-client)
            # We run it in executor to not block async loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._clob_client.create_and_post_order(order_args)
            )
            
            if result and result.get('orderID'):
                return {
                    'success': True,
                    'tx_hash': result.get('orderID') or result.get('transactionHash', 'unknown'),
                    'order_id': result.get('orderID')
                }
            else:
                return {
                    'success': False,
                    'error': f"Order rejected: {result}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# Global executor instance
executor = TradeExecutor()
