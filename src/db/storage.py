"""
SQLite async database layer for trade storage.
Replaces MongoDB with lightweight local storage.
Uses WAL mode for better concurrency.
"""
import aiosqlite
import asyncio
import json
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

from src.config import settings


@dataclass
class TradeRecord:
    """Represents a copied trade."""
    id: Optional[int] = None
    market_id: str = ""
    market_name: str = ""
    side: str = ""  # BUY or SELL
    size_usdc: float = 0.0
    price: float = 0.0
    status: str = ""  # COPIED, FAILED, PENDING
    error_message: Optional[str] = None
    timestamp: str = ""
    tx_hash: Optional[str] = None
    latency_ms: float = 0.0
    pnl: float = 0.0


@dataclass 
class SignalRecord:
    """Represents a detected signal from target wallet."""
    id: Optional[int] = None
    tx_hash: str = ""
    market_id: str = ""
    market_name: str = ""
    maker: str = ""
    side: str = ""
    amount: float = 0.0
    price: float = 0.0
    timestamp: str = ""
    processed: bool = False


class Database:
    """
    Async SQLite database manager.
    Uses WAL mode and connection locking to prevent 'database is locked' errors.
    """
    
    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()  # Prevent concurrent writes
    
    async def connect(self):
        """Initialize database connection and create tables."""
        # Handle Database Reset
        if settings.RESET_DB and os.path.exists(self.db_path):
            try:
                print(f"♻️  RESETTING DATABASE: {self.db_path}")
                os.remove(self.db_path)
                if os.path.exists(f"{self.db_path}-wal"):
                    os.remove(f"{self.db_path}-wal")
                if os.path.exists(f"{self.db_path}-shm"):
                    os.remove(f"{self.db_path}-shm")
            except Exception as e:
                print(f"❌ Failed to reset database: {e}")

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Connect with timeout and isolation level
        self._connection = await aiosqlite.connect(
            self.db_path,
            timeout=30.0,  # 30 second timeout
            isolation_level=None  # Autocommit mode
        )
        self._connection.row_factory = aiosqlite.Row
        
        # Enable WAL mode for better concurrency
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        
        # Create tables
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                market_name TEXT,
                side TEXT NOT NULL,
                size_usdc REAL NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                timestamp TEXT NOT NULL,
                tx_hash TEXT,
                latency_ms REAL DEFAULT 0,
                pnl REAL DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                market_id TEXT NOT NULL,
                market_name TEXT,
                maker TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                timestamp TEXT NOT NULL,
                processed INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                successful_trades INTEGER DEFAULT 0,
                failed_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                total_volume REAL DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            CREATE INDEX IF NOT EXISTS idx_signals_processed ON signals(processed);
        """)
    
    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
    
    # === Trade Operations ===
    
    async def insert_trade(self, trade: TradeRecord) -> int:
        """Insert a new trade record."""
        async with self._lock:
            cursor = await self._connection.execute("""
                INSERT INTO trades (market_id, market_name, side, size_usdc, price, 
                                  status, error_message, timestamp, tx_hash, latency_ms, pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trade.market_id, trade.market_name, trade.side, trade.size_usdc,
                  trade.price, trade.status, trade.error_message, trade.timestamp,
                  trade.tx_hash, trade.latency_ms, trade.pnl))
            return cursor.lastrowid
    
    async def get_recent_trades(self, limit: int = 50) -> list[TradeRecord]:
        """Get most recent trades."""
        cursor = await self._connection.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [TradeRecord(**dict(row)) for row in rows]
    
    async def get_trades_since(self, since: datetime) -> list[TradeRecord]:
        """Get trades since a specific datetime."""
        cursor = await self._connection.execute(
            "SELECT * FROM trades WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since.isoformat(),)
        )
        rows = await cursor.fetchall()
        return [TradeRecord(**dict(row)) for row in rows]
    
    # === Signal Operations ===
    
    async def insert_signal(self, signal: SignalRecord) -> bool:
        """Insert a new signal if not already exists."""
        async with self._lock:
            try:
                await self._connection.execute("""
                    INSERT INTO signals (tx_hash, market_id, market_name, maker, side, 
                                       amount, price, timestamp, processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (signal.tx_hash, signal.market_id, signal.market_name, signal.maker,
                      signal.side, signal.amount, signal.price, signal.timestamp, 0))
                return True
            except aiosqlite.IntegrityError:
                return False  # Already exists
    
    async def get_unprocessed_signals(self) -> list[SignalRecord]:
        """Get all unprocessed signals."""
        cursor = await self._connection.execute(
            "SELECT * FROM signals WHERE processed = 0 ORDER BY timestamp ASC"
        )
        rows = await cursor.fetchall()
        return [SignalRecord(**dict(row)) for row in rows]
    
    async def mark_signal_processed(self, tx_hash: str):
        """Mark a signal as processed."""
        async with self._lock:
            await self._connection.execute(
                "UPDATE signals SET processed = 1 WHERE tx_hash = ?", (tx_hash,)
            )
    
    async def signal_exists(self, tx_hash: str) -> bool:
        """Check if a signal already exists."""
        cursor = await self._connection.execute(
            "SELECT 1 FROM signals WHERE tx_hash = ?", (tx_hash,)
        )
        return await cursor.fetchone() is not None
    
    # === Statistics ===
    
    async def get_today_stats(self) -> dict:
        """Get today's trading statistics."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cursor = await self._connection.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN status = 'COPIED' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                COALESCE(SUM(pnl), 0) as total_pnl,
                COALESCE(SUM(size_usdc), 0) as total_volume
            FROM trades 
            WHERE date(timestamp) = ?
        """, (today,))
        row = await cursor.fetchone()
        return dict(row) if row else {
            "total_trades": 0, "successful": 0, "failed": 0,
            "total_pnl": 0.0, "total_volume": 0.0
        }
    
    async def get_total_exposure(self) -> float:
        """Calculate current total exposure (open positions)."""
        # Simplified: sum of all BUY trades - SELL trades
        cursor = await self._connection.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN side = 'BUY' THEN size_usdc 
                     WHEN side = 'SELL' THEN -size_usdc 
                     ELSE 0 END
            ), 0) as exposure
            FROM trades WHERE status = 'COPIED'
        """)
        row = await cursor.fetchone()
        return max(0, row["exposure"]) if row else 0.0


# Global database instance
db = Database()
