"""
Logging module - File and console logging for the bot.
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Log file path with date
LOG_FILE = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y-%m-%d')}.log")


def setup_logger(name: str = "copybot") -> logging.Logger:
    """
    Set up and return a logger that writes to both file and console.
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # File handler - rotating, max 10MB, keep 5 backups
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Format
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_handler.setFormatter(file_format)
    console_handler.setFormatter(console_format)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Global logger instance
logger = setup_logger()


def log(level: str, message: str):
    """
    Log a message at the specified level.
    Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    level = level.upper()
    if level == "DEBUG":
        logger.debug(message)
    elif level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    elif level == "CRITICAL":
        logger.critical(message)
    else:
        logger.info(message)


def log_trade(side: str, market: str, amount: float, price: float, status: str):
    """Log a trade with structured format."""
    logger.info(f"TRADE | {side} | {market} | ${amount:.2f} @ {price:.2f} | {status}")


def log_signal(side: str, market: str, amount: float, price: float):
    """Log a detected signal."""
    logger.info(f"SIGNAL | {side} | {market} | ${amount:.2f} @ {price:.2f}")


def log_risk(reason: str, details: str = ""):
    """Log a risk event."""
    logger.warning(f"RISK | {reason} | {details}")


def log_error(component: str, error: str):
    """Log an error."""
    logger.error(f"ERROR | {component} | {error}")
