"""
WebSocket Client for Polymarket CLOB real-time data.
Based on official Polymarket documentation.
"""
import asyncio
import json
from datetime import datetime
from typing import Callable, Optional, Dict
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from src.config import settings
from src.db import SignalRecord


# Try to import py-clob-client for API key generation
CLOB_AVAILABLE = False
try:
    from py_clob_client.client import ClobClient
    CLOB_AVAILABLE = True
except ImportError:
    pass


class PolymarketWebSocket:
    """
    Real-time WebSocket connection to Polymarket CLOB.
    
    Channels:
    - "market": Orderbook and price updates (public)
    - "user": User's order/trade updates (requires auth)
    """
    
    MARKET_CHANNEL = "market"
    USER_CHANNEL = "user"
    
    def __init__(self):
        self._ws = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        
        # API credentials (derived from ClobClient)
        self._api_key = ""
        self._api_secret = ""
        self._api_passphrase = ""
        
        # Callbacks
        self._on_trade: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._on_price: Optional[Callable] = None
        
        # Stats
        self.connected = False
        self.messages_received = 0
        self.trades_received = 0
        self.last_message: Optional[datetime] = None
        self.reconnect_count = 0
        
        # Track known trades to avoid duplicates
        self._known_trades: set = set()
    
    def set_callbacks(
        self,
        on_trade: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_price: Optional[Callable] = None
    ):
        """Set callback functions."""
        self._on_trade = on_trade
        self._on_log = on_log
        self._on_price = on_price
    
    async def _log(self, level: str, message: str):
        """Internal logging."""
        if self._on_log:
            await self._on_log(level, message)
    
    def _derive_api_keys(self):
        """Derive API keys from ClobClient."""
        if not CLOB_AVAILABLE:
            return False
        
        try:
            client = ClobClient(
                host=settings.CLOB_HTTP_URL,
                key=settings.PRIVATE_KEY,
                chain_id=137,
                signature_type=2,  # Browser wallet type
                funder=settings.PROXY_WALLET
            )
            
            creds = client.derive_api_key()
            self._api_key = creds.get("apiKey", "")
            self._api_secret = creds.get("secret", "")
            self._api_passphrase = creds.get("passphrase", "")
            return True
        except Exception as e:
            return False
    
    async def start(self):
        """Start WebSocket connection."""
        if self._running:
            return
        
        self._running = True
        
        # Derive API keys for authenticated channels
        await self._log("INFO", "🔌 WebSocket client starting...")
        
        if CLOB_AVAILABLE and settings.PRIVATE_KEY:
            if self._derive_api_keys():
                await self._log("INFO", "🔑 API keys derived for WebSocket auth")
            else:
                await self._log("WARNING", "Could not derive API keys")
        
        self._task = asyncio.create_task(self._connection_loop())
    
    async def stop(self):
        """Stop WebSocket connection."""
        self._running = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.connected = False
        await self._log("INFO", "🔌 WebSocket disconnected")
    
    async def _connection_loop(self):
        """Main connection loop with auto-reconnect."""
        while self._running:
            try:
                await self._connect_and_listen()
            except ConnectionClosed as e:
                self.connected = False
                await self._log("WARNING", f"WebSocket closed: {e.code}")
            except WebSocketException as e:
                self.connected = False
                await self._log("ERROR", f"WebSocket error: {e}")
            except Exception as e:
                self.connected = False
                await self._log("ERROR", f"Connection error: {e}")
            
            if self._running:
                await self._log("INFO", f"Reconnecting in {self._reconnect_delay:.0f}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
                self.reconnect_count += 1
    
    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages."""
        # Use USER channel for trade notifications
        channel = self.USER_CHANNEL
        ws_url = f"{settings.CLOB_WS_URL}/ws/{channel}"
        
        await self._log("INFO", f"🔗 Connecting to {channel} channel...")
        
        async with websockets.connect(
            ws_url,
            ping_interval=None,  # We handle pings manually
            ping_timeout=None,
            close_timeout=5
        ) as ws:
            self._ws = ws
            self.connected = True
            self._reconnect_delay = 1.0
            
            await self._log("INFO", "✅ WebSocket connected!")
            
            # Subscribe to user channel
            await self._subscribe()
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            # Listen for messages
            async for message in ws:
                await self._handle_message(message)
    
    async def _subscribe(self):
        """Subscribe to user's trade updates."""
        if not self._ws:
            return
        
        # Auth object for user channel
        auth = {}
        if self._api_key:
            auth = {
                "apiKey": self._api_key,
                "secret": self._api_secret,
                "passphrase": self._api_passphrase
            }
        
        # Subscribe message
        subscribe_msg = {
            "type": self.USER_CHANNEL,
            "markets": [],  # Empty = all markets
            "auth": auth
        }
        
        await self._ws.send(json.dumps(subscribe_msg))
        await self._log("INFO", f"📡 Subscribed to user trades")
    
    async def _ping_loop(self):
        """Send PING every 10 seconds as per Polymarket docs."""
        while self._running and self._ws:
            try:
                await asyncio.sleep(10)
                if self._ws:
                    await self._ws.send("PING")
            except Exception:
                break
    
    async def _handle_message(self, raw_message: str):
        """Process incoming WebSocket message."""
        self.messages_received += 1
        self.last_message = datetime.utcnow()
        
        # Ignore PONG responses
        if raw_message == "PONG":
            return
        
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        
        msg_type = data.get("type") or data.get("event")
        
        # Handle trade/fill messages
        if msg_type in ["trade", "fill", "order_fill", "user_trade", "trade_notification"]:
            await self._handle_trade_message(data)
        elif msg_type == "error":
            await self._log("ERROR", f"WebSocket error: {data.get('message', data)}")
        elif msg_type in ["subscribed", "subscription", "connected"]:
            await self._log("DEBUG", f"WS: {msg_type}")
    
    async def _handle_trade_message(self, data: dict):
        """Process a trade/fill message."""
        self.trades_received += 1
        
        trade_data = data.get("data") or data.get("trade") or data
        
        # Parse into signal
        signal = self._parse_ws_trade(trade_data)
        
        if signal:
            # Skip if already seen
            if signal.tx_hash in self._known_trades:
                return
            self._known_trades.add(signal.tx_hash)
            
            if self._on_trade:
                await self._log("INFO", f"🎯 WS TRADE: {signal.side} {signal.market_name}")
                await self._on_trade(signal)
    
    def _parse_ws_trade(self, data: dict) -> Optional[SignalRecord]:
        """Parse WebSocket trade into SignalRecord."""
        try:
            tx_hash = (
                data.get("id") or
                data.get("trade_id") or
                data.get("transaction_hash") or
                f"ws_{datetime.utcnow().timestamp()}"
            )
            
            market_id = (
                data.get("market") or
                data.get("token_id") or
                data.get("asset_id") or
                "unknown"
            )
            
            market_name = (
                data.get("market_name") or
                data.get("title") or
                data.get("question") or
                str(market_id)[:30]
            )
            
            side = str(data.get("side", "BUY")).upper()
            if side not in ["BUY", "SELL"]:
                side = "BUY"
            
            try:
                amount = float(data.get("size") or data.get("amount") or 0)
            except:
                amount = 0
            
            try:
                price = float(data.get("price") or 0)
            except:
                price = 0
            
            return SignalRecord(
                tx_hash=str(tx_hash),
                market_id=str(market_id),
                market_name=str(market_name),
                maker=settings.USER_ADDRESS,
                side=side,
                amount=amount,
                price=price,
                timestamp=datetime.utcnow().isoformat(),
                processed=False
            )
        except Exception:
            return None


# Global WebSocket instance
polymarket_ws = PolymarketWebSocket()
