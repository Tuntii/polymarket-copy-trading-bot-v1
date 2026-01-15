# Polymarket Copy Trading Bot 🤖

A terminal-based copy trading bot for Polymarket with a beautiful TUI (Terminal User Interface).

![TUI Screenshot](docs/screenshot.png)

## ✨ Features

- **🖥️ Beautiful Terminal UI** - Built with [Textual](https://textual.textualize.io/)
- **⚡ Real-time Updates** - Live trade detection and status updates
- **🛡️ Risk Management** - Comprehensive risk checks and position limits
- **📊 Live Metrics** - Balance, exposure, and P/L tracking
- **📝 Trade History** - Complete trade log with latency tracking
- **🧪 Paper Trading** - Test without real money

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure:
```env
USER_ADDRESS=0x...        # Target wallet to copy
PROXY_WALLET=0x...        # Your Polymarket wallet
PRIVATE_KEY=0x...         # Your private key
PAPER_TRADING=true        # Start in paper mode
```

### 3. Run the Bot
```bash
python main.py
```

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `S` | Start/Stop bot |
| `C` | Clear logs |
| `R` | Refresh UI |
| `H` | Show help |
| `Q` | Quit |

## 📁 Project Structure

```
polymarket-copy-trading-bot-v1/
├── main.py              # Entry point
├── requirements.txt     # Dependencies
├── .env                 # Configuration
├── src/
│   ├── config.py        # Settings via pydantic
│   ├── core/            # Bot logic
│   │   ├── bot.py       # Main controller
│   │   ├── monitor.py   # Trade detection
│   │   ├── executor.py  # Trade execution
│   │   └── risk.py      # Risk management
│   ├── db/
│   │   └── storage.py   # SQLite storage
│   └── ui/
│       ├── app.py       # Textual app
│       └── widgets/     # UI components
└── data/
    └── bot.db           # SQLite database
```

## ⚙️ Configuration

All settings are configured via `.env` file:

### Wallet Settings
- `USER_ADDRESS` - Target wallet address to copy
- `PROXY_WALLET` - Your Polymarket wallet address
- `PRIVATE_KEY` - Your wallet private key

### Risk Limits
- `MAX_POSITION_SIZE_USDC` - Maximum single trade size
- `MAX_TOTAL_EXPOSURE_USDC` - Maximum total exposure
- `MAX_DAILY_LOSS_USDC` - Daily loss limit

### Trading
- `PAPER_TRADING` - Enable paper trading mode
- `FETCH_INTERVAL` - Polling interval in seconds
- `COPY_RATIO_PERCENT` - Percentage of trade to copy

## 🧪 Paper Trading Mode

When `PAPER_TRADING=true`:
- No real trades are executed
- Mock signals are generated for testing
- All metrics and logs work normally
- Perfect for testing your configuration

## 🔧 Development

### Running Tests
```bash
pytest tests/
```

### Textual Dev Mode
```bash
textual run --dev main.py
```

## ⚠️ Disclaimer

This bot is for educational purposes. Trading cryptocurrencies and prediction markets involves significant risk. Always:
- Start with paper trading
- Never trade more than you can afford to lose
- Understand the risks before live trading

## 📄 License

MIT License - See LICENSE file for details.
