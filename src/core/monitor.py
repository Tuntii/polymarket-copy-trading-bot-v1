"""
Trade Monitor - Watches target wallet for new trades.
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Callable, Optional
import httpx

from src.config import settings
from src.db import db, SignalRecord


class TradeMonitor:
    """
    Monitors target wallet address for new trades.
    In paper mode, generates mock signals for testing.
    
    IMPORTANT: Only processes trades that occur AFTER the bot starts.
    Historical trades are ignored to prevent unwanted position entries.
    """
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_signal: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._client: Optional[httpx.AsyncClient] = None
        
        # Start time - trades before this are IGNORED
        self._start_time: Optional[datetime] = None
        
        # Skip first batch - ONLY process trades that come AFTER first API call
        self._first_run = True
        self._known_tx_hashes: set = set()  # Track already seen trades
        
        # Stats
        self.signals_detected = 0
        self.signals_skipped_old = 0  # Counter for skipped old trades
        self.api_calls = 0
        self.last_check: Optional[datetime] = None
        self.errors = 0
        self.last_api_response: str = ""
    
    def set_signal_callback(self, callback: Callable):
        """Set callback function for new signals."""
        self._on_signal = callback
    
    def set_log_callback(self, callback: Callable):
        """Set callback for log messages."""
        self._on_log = callback
    
    async def _log(self, level: str, message: str):
        """Internal logging."""
        if self._on_log:
            await self._on_log(level, message)
    
    async def start(self):
        """Start monitoring loop."""
        if self._running:
            return
        
        self._running = True
        # Record start time - only trades AFTER this will be processed
        self._start_time = datetime.utcnow()
        self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """Stop monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        # Log initial status
        mode = "PAPER" if settings.PAPER_TRADING else "LIVE"
        await self._log("INFO", f"📡 Monitor started in {mode} mode")
        await self._log("INFO", f"👀 Watching wallet: {settings.USER_ADDRESS[:16]}...")
        await self._log("INFO", "⏳ Capturing existing trades (will ignore)...")
        
        while self._running:
            try:
                self.last_check = datetime.utcnow()
                self.api_calls += 1
                
                signals = await self._fetch_target_activity()
                
                # === FIRST RUN: Capture all existing trades as "known" ===
                if self._first_run:
                    for signal in signals:
                        self._known_tx_hashes.add(signal.tx_hash)
                    self._first_run = False
                    await self._log("INFO", f"✅ Captured {len(self._known_tx_hashes)} existing trades - will ignore them")
                    await self._log("INFO", "🎯 Now watching for NEW trades only...")
                    await asyncio.sleep(settings.FETCH_INTERVAL)
                    continue
                
                # Log API result periodically (every 10 calls)
                if self.api_calls % 10 == 1:
                    if settings.PAPER_TRADING:
                        await self._log("DEBUG", f"📝 Paper mode - mock signal chance")
                    else:
                        await self._log("DEBUG", f"🔍 API check #{self.api_calls} - {len(signals)} trades")
                
                for signal in signals:
                    # === Skip already known trades ===
                    if signal.tx_hash in self._known_tx_hashes:
                        continue
                    
                    # Add to known set
                    self._known_tx_hashes.add(signal.tx_hash)
                    
                    # === CRITICAL: Skip trades from BEFORE bot started ===
                    if not self._is_trade_valid(signal):
                        self.signals_skipped_old += 1
                        await self._log("DEBUG", f"⏭️ Skipped old trade: {signal.tx_hash[:16]}...")
                        continue
                    
                    # Check if already in database
                    exists = await db.signal_exists(signal.tx_hash)
                    if not exists:
                        # New signal detected
                        await db.insert_signal(signal)
                        self.signals_detected += 1
                        
                        await self._log("INFO", f"🎯 NEW SIGNAL: {signal.side} {signal.market_name} @ ${signal.price:.2f}")
                        
                        # Notify callback
                        if self._on_signal:
                            await self._on_signal(signal)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.errors += 1
                await self._log("ERROR", f"Monitor error: {e}")
                await asyncio.sleep(1)
            
            await asyncio.sleep(settings.FETCH_INTERVAL)
    
    def _is_trade_valid(self, signal: SignalRecord) -> bool:
        """
        Check if a trade should be processed.
        
        Returns False if:
        1. Trade timestamp is BEFORE bot started (historical trade)
        2. Trade is older than TOO_OLD_MINUTES setting
        
        This prevents copying old/historical trades when bot starts.
        """
        if not self._start_time:
            return False
        
        # Parse signal timestamp
        try:
            if isinstance(signal.timestamp, str):
                signal_time = datetime.fromisoformat(signal.timestamp.replace("Z", "+00:00"))
                # Remove timezone info for comparison if present
                if signal_time.tzinfo:
                    signal_time = signal_time.replace(tzinfo=None)
            else:
                signal_time = signal.timestamp
        except:
            # If we can't parse, reject to be safe
            return False
        
        # CHECK 1: Must be AFTER bot started
        if signal_time < self._start_time:
            return False
        
        # CHECK 2: Must not be older than TOO_OLD_MINUTES
        max_age = timedelta(minutes=settings.TOO_OLD_MINUTES)
        if datetime.utcnow() - signal_time > max_age:
            return False
        
        return True
    
    async def _fetch_target_activity(self) -> list[SignalRecord]:
        """
        Fetch recent trades from target wallet via Polymarket CLOB API.
        
        Uses the trades endpoint to get maker fills for the target address.
        """
        if settings.PAPER_TRADING:
            # Paper trading mode - generate mock signals
            if random.random() < 0.1:
                return [self._generate_mock_signal()]
            return []
        
        # === REAL POLYMARKET API IMPLEMENTATION ===
        signals = []
        
        try:
            # Polymarket CLOB API - Get trades for target wallet
            # Documentation: https://docs.polymarket.com/
            base_url = settings.CLOB_HTTP_URL.rstrip('/')
            
            # Endpoint to fetch user's trade history
            # Try multiple endpoints as Polymarket API can vary
            endpoints = [
                f"{base_url}/trades?maker={settings.USER_ADDRESS}&limit=50",
                f"{base_url}/data/trades?maker={settings.USER_ADDRESS}",
            ]
            
            response = None
            for endpoint in endpoints:
                try:
                    response = await self._client.get(
                        endpoint,
                        headers={
                            "Accept": "application/json",
                            "User-Agent": "PolymarketCopyBot/1.0"
                        }
                    )
                    if response.status_code == 200:
                        break
                except:
                    continue
            
            if not response or response.status_code != 200:
                # Try the activity endpoint as fallback
                activity_url = f"https://data-api.polymarket.com/activity?user={settings.USER_ADDRESS}&limit=50"
                response = await self._client.get(activity_url)
            
            if response.status_code != 200:
                self.errors += 1
                return []
            
            data = response.json()
            
            # Parse trades from response
            # Handle both array response and object with 'data' field
            trades = data if isinstance(data, list) else data.get('data', data.get('trades', []))
            
            for trade in trades:
                try:
                    signal = self._parse_trade(trade)
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    # Skip malformed trades
                    continue
            
        except httpx.TimeoutException:
            self.errors += 1
        except httpx.RequestError as e:
            self.errors += 1
        except Exception as e:
            self.errors += 1
        
        return signals
    
    def _parse_trade(self, trade: dict) -> SignalRecord | None:
        """
        Parse a trade from Polymarket API response into SignalRecord.
        
        Polymarket trade structure (approximate):
        {
            "id": "trade_id",
            "taker_order_id": "...",
            "maker_order_id": "...",
            "market": "0x...",
            "asset_id": "...",
            "side": "BUY" or "SELL",
            "size": "100.5",
            "price": "0.65",
            "timestamp": 1234567890,
            "transaction_hash": "0x...",
            ...
        }
        """
        if not trade:
            return None
        
        # Extract transaction hash (used as unique identifier)
        tx_hash = (
            trade.get('transaction_hash') or 
            trade.get('transactionHash') or 
            trade.get('hash') or 
            trade.get('id') or
            f"trade_{trade.get('timestamp', datetime.utcnow().timestamp())}"
        )
        
        # Extract market ID
        market_id = (
            trade.get('market') or 
            trade.get('market_id') or 
            trade.get('marketId') or
            trade.get('asset_id') or
            trade.get('token_id') or
            "unknown"
        )
        
        # Extract market name (may not always be present)
        market_name = (
            trade.get('market_name') or 
            trade.get('marketName') or 
            trade.get('title') or
            trade.get('question') or
            market_id[:20] + "..."
        )
        
        # Extract side (BUY/SELL)
        side = str(trade.get('side', 'BUY')).upper()
        if side not in ['BUY', 'SELL']:
            side = 'BUY'
        
        # Extract size/amount
        try:
            amount = float(trade.get('size') or trade.get('amount') or trade.get('qty') or 0)
        except:
            amount = 0
        
        # Extract price
        try:
            price = float(trade.get('price') or trade.get('avg_price') or 0)
        except:
            price = 0
        
        # Extract timestamp
        ts = trade.get('timestamp') or trade.get('created_at') or trade.get('time')
        if isinstance(ts, (int, float)):
            # Unix timestamp
            if ts > 1e12:  # milliseconds
                ts = ts / 1000
            timestamp = datetime.utcfromtimestamp(ts).isoformat()
        elif isinstance(ts, str):
            timestamp = ts
        else:
            timestamp = datetime.utcnow().isoformat()
        
        # Extract maker address
        maker = (
            trade.get('maker') or 
            trade.get('maker_address') or 
            trade.get('user') or
            settings.USER_ADDRESS
        )
        
        return SignalRecord(
            tx_hash=str(tx_hash),
            market_id=str(market_id),
            market_name=str(market_name),
            maker=str(maker),
            side=side,
            amount=amount,
            price=price,
            timestamp=timestamp,
            processed=False
        )
    
    def _generate_mock_signal(self) -> SignalRecord:
        """Generate a mock signal for paper trading."""
        markets = [
            ("0xmarket1", "Trump wins 2024"),
            ("0xmarket2", "ETH > $4000 by March"),
            ("0xmarket3", "Fed cuts rates in Q1"),
            ("0xmarket4", "Bitcoin hits $100k"),
            ("0xmarket5", "AI company IPO in 2024"),
        ]
        
        market_id, market_name = random.choice(markets)
        
        return SignalRecord(
            tx_hash=f"0x{random.randint(10**15, 10**16):x}",
            market_id=market_id,
            market_name=market_name,
            maker=settings.USER_ADDRESS or "0xTargetWallet",
            side=random.choice(["BUY", "SELL"]),
            amount=round(random.uniform(10, 100), 2),
            price=round(random.uniform(0.1, 0.9), 2),
            timestamp=datetime.utcnow().isoformat(),
            processed=False
        )


# Global monitor instance
monitor = TradeMonitor()
