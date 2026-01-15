# AGENTS.md - AI Agent Guide for Polymarket Copy Trading Bot

Bu doküman, AI asistanların bu codebase üzerinde çalışırken referans olarak kullanması için hazırlanmıştır.

## 📁 Proje Yapısı

```
polymarket-copy-trading-bot-v1/
├── main.py              # Entry point - TUI uygulamasını başlatır
├── requirements.txt     # Python bağımlılıkları
├── .env                 # Ortam değişkenleri
├── src/
│   ├── __init__.py
│   ├── config.py        # Pydantic-settings tabanlı konfigürasyon
│   ├── core/            # Çekirdek Bot Mantığı
│   │   ├── __init__.py
│   │   ├── bot.py       # BotEngine - ana kontrol sınıfı
│   │   ├── monitor.py   # TradeMonitor - hedef cüzdan izleme
│   │   ├── executor.py  # TradeExecutor - trade kopyalama
│   │   └── risk.py      # RiskManager - risk yönetimi
│   ├── db/
│   │   ├── __init__.py
│   │   └── storage.py   # SQLite async storage
│   └── ui/
│       ├── __init__.py
│       ├── app.py       # Textual App - ana TUI uygulaması
│       └── widgets/     # TUI widget'ları
│           ├── __init__.py
│           ├── status_panel.py
│           ├── risk_panel.py
│           ├── trade_table.py
│           └── log_panel.py
└── data/
    └── bot.db           # SQLite veritabanı (otomatik oluşur)
```

## 🔧 Teknoloji Stack'i

- **TUI Framework**: Textual (Rich tabanlı)
- **Async Runtime**: asyncio
- **Database**: SQLite (aiosqlite)
- **Settings**: pydantic-settings
- **HTTP Client**: httpx
- **Polymarket API**: py-clob-client

## 🧩 Core Modüller

### BotEngine (`src/core/bot.py`)
Ana bot kontrol sınıfı. Tüm bileşenleri orkestre eder.

```python
class BotEngine:
    async def start()        # Botu başlat
    async def stop()         # Botu durdur
    async def toggle()       # Durumu değiştir
    def get_status()         # BotStatus döner
    async def get_risk_metrics()  # RiskMetrics döner
```

### TradeMonitor (`src/core/monitor.py`)
Hedef cüzdanı polling ile izler. Paper mode'da mock sinyal üretir.

```python
class TradeMonitor:
    async def start()
    async def stop()
    async def _fetch_target_activity() -> list[SignalRecord]
```

### TradeExecutor (`src/core/executor.py`)
Sinyalleri işler, risk kontrolü yapar ve trade kopyalar.

```python
class TradeExecutor:
    async def start()
    async def stop()
    async def _execute_signal(signal: SignalRecord)
```

### RiskManager (`src/core/risk.py`)
Her trade öncesi risk kontrolü yapar.

```python
class RiskManager:
    async def check_trade(amount_usdc: float) -> Tuple[bool, str]
    async def get_metrics() -> RiskMetrics
```

### Database (`src/db/storage.py`)
SQLite async veritabanı katmanı.

```python
class Database:
    async def connect()
    async def close()
    async def insert_trade(trade: TradeRecord)
    async def get_recent_trades(limit: int) -> list[TradeRecord]
    async def insert_signal(signal: SignalRecord)
    async def get_unprocessed_signals() -> list[SignalRecord]
```

## 🖥️ TUI Yapısı

### Ana Uygulama (`src/ui/app.py`)
Textual App sınıfı. Layout ve keyboard binding'leri yönetir.

### Widget'lar (`src/ui/widgets/`)
- **StatusPanel**: Bot durumu, uptime, wallet bilgileri
- **RiskPanel**: Risk metrikleri, exposure bar
- **TradeTable**: Trade geçmişi tablosu
- **LogPanel**: Canlı log görüntüleyici

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `S` | Bot başlat/durdur |
| `C` | Logları temizle |
| `R` | UI yenile |
| `H` | Yardım göster |
| `Q` | Çıkış |

## ⚙️ Konfigürasyon (.env)

```env
# Cüzdan Ayarları
USER_ADDRESS=<hedef_cuzdan>
PROXY_WALLET=<kendi_cuzdan>
PRIVATE_KEY=<private_key>

# API
CLOB_HTTP_URL=https://clob.polymarket.com/
RPC_URL=<polygon_rpc>

# Mod
PAPER_TRADING=true

# Risk Limitleri
MAX_POSITION_SIZE_USDC=5.0
MAX_TOTAL_EXPOSURE_USDC=50.0
MAX_DAILY_LOSS_USDC=25.0

# Polling
FETCH_INTERVAL=1.0
```

## 🚀 Çalıştırma

```bash
# Bağımlılıkları kur
pip install -r requirements.txt

# Botu çalıştır
python main.py
```

## 🔄 Veri Akışı

```
TradeMonitor (polling/mock)
         ↓
    SignalRecord → SQLite
         ↓
    TradeExecutor
         ↓
    RiskManager.check_trade()
         ↓
   [PASS]        [FAIL]
     ↓              ↓
  Execute     Log rejection
     ↓
  TradeRecord → SQLite → TUI
```

## 📝 Geliştirme İpuçları

- **Yeni widget eklemek**: `src/ui/widgets/` klasörüne ekle, `__init__.py` güncelle
- **Risk kuralı eklemek**: `src/core/risk.py` → `check_trade()` metoduna ekle
- **Yeni env değişkeni**: `src/config.py` → `Settings` sınıfına ekle
- **Gerçek API entegrasyonu**: `src/core/monitor.py` → `_fetch_target_activity()` metodunu güncelle

## 🧪 Test Modu

`PAPER_TRADING=true` ile:
- Gerçek işlem yapılmaz
- %10 ihtimalle mock sinyal üretilir
- Tüm loglar ve metrikler normal çalışır

## ⚠️ Dikkat Edilecekler

1. **Textual sürümü**: >= 0.47.0 gerekli
2. **Terminal boyutu**: Minimum 80x24 önerilir
3. **SQLite**: `data/bot.db` otomatik oluşturulur
4. **Async**: Tüm core modüller async, UI ile uyumlu
