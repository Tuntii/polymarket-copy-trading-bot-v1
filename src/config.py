"""
Application configuration using pydantic-settings.
Reads from .env file in project root.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration with environment variable support."""
    
    # === Wallet Configuration ===
    USER_ADDRESS: str = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"  # Target wallet to copy
    PROXY_WALLET: str = "0xE0bf757061ae4F3847E836CC5c94eDafF45110f0"  # Your Polymarket wallet
    PRIVATE_KEY: str = "0x4789eeec4669700d77f360bc208c4b90617ba4ae679fe5ef474b400a175ba473"   # Your private key
    
    # === Polymarket API ===
    CLOB_HTTP_URL: str = "https://clob.polymarket.com/"
    CLOB_WS_URL: str = "wss://ws-subscriptions-clob.polymarket.com/ws"
    RPC_URL: str = "https://polygon-mainnet.infura.io/v3/8f2020a1d5284a139fa22ae8a99af2cc"
    USDC_CONTRACT_ADDRESS: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    # === Database ===
    DATABASE_PATH: str = "data/bot.db"
    
    # === Polling ===
    FETCH_INTERVAL: float = 1.0  # seconds
    TOO_OLD_MINUTES: int = 15    # Skip trades older than this
    RETRY_LIMIT: int = 3
    
    # === Trading Mode ===
    PAPER_TRADING: bool = False
    
    # === Risk Limits (Conservative for $30 balance) ===
    MAX_POSITION_SIZE_USDC: float = 2.0      # Max $2 per trade
    MAX_TOTAL_EXPOSURE_USDC: float = 15.0    # Max $15 total open (50% of balance)
    MIN_TRADE_AMOUNT_USDC: float = 0.5       # Min $0.50 trade size
    MAX_DAILY_LOSS_USDC: float = 5.0         # Stop if lose $5 in a day
    MAX_DAILY_LOSS_PERCENT: float = 15.0     # Or 15% of balance
    STOP_LOSS_PERCENT: float = 20.0          # Circuit breaker at 20% drawdown
    TAKE_PROFIT_PERCENT: float = 50.0        # Take profit at 50% gain
    
    # === Copy Ratio (IMPORTANT: How much to copy) ===
    # If trader enters $100, you enter $100 * 1.5% = $1.50
    COPY_RATIO_PERCENT: float = 1.5          # Copy only 1.5% of original trade
    FIXED_TRADE_AMOUNT: float = 0.0          # If > 0, always trade this amount (e.g. 2.0 = $2 every time)
    
    # === Slippage Protection ===
    MAX_SLIPPAGE_PERCENT: float = 2.0
    MAX_PRICE_DIFFERENCE_PERCENT: float = 5.0
    SKIP_IF_PRICE_CHANGED_PERCENT: float = 10.0
    
    # === Trade Frequency ===
    MIN_TIME_BETWEEN_TRADES_MS: int = 3000   # 3 seconds between trades
    MAX_TRADES_PER_HOUR: int = 10            # Max 10 trades/hour
    MAX_TRADES_PER_DAY: int = 30             # Max 30 trades/day
    
    # === Balance Protection ===
    MIN_BALANCE_TO_KEEP_USDC: float = 5.0    # Always keep $5 reserve
    MAX_BALANCE_USAGE_PERCENT: float = 60.0  # Use max 60% of balance
    
    # === UI Settings ===
    LOG_LEVEL: str = "INFO"
    MAX_LOG_LINES: int = 100
    REFRESH_RATE_MS: int = 500
    
    # === System ===
    RESET_DB: bool = False
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
        env_file_encoding='utf-8',
        extra='ignore'
    )


# Global settings instance
settings = Settings()
