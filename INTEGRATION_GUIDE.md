# Bot ve Dashboard Entegrasyon Rehberi

## ✅ Tamamlanan Entegrasyonlar

### 1. **Gerçek Veri Entegrasyonu**
- ❌ Tüm mockup veriler kaldırıldı
- ✅ API server gerçek bot state'ini döndürüyor
- ✅ Wallet adresleri ENV'den dinamik olarak alınıyor
- ✅ Risk metrikleri RiskManager'dan gerçek zamanlı çekiliyor

### 2. **Real-time Monitoring**
- ✅ WebSocket ile canlı log akışı
- ✅ Trade detection gerçek zamanlı
- ✅ Dashboard ile bot durumu senkronize

### 3. **Trade Tracking**
- ✅ Her trade attempt tracked ve dashboard'a gönderiliyor
- ✅ Success/Failed durumları görüntüleniyor
- ✅ Latency bilgisi eklendi
- ✅ Trade details (market, side, size, price) tam olarak gösteriliyor

### 4. **Risk Management Visualization**
- ✅ Current balance görüntüleme
- ✅ Total exposure tracking
- ✅ Daily loss monitoring
- ✅ Risk level (LOW/MEDIUM/HIGH) dinamik hesaplama

### 5. **Bot Control**
- ✅ Dashboard'dan Start/Stop butonu
- ✅ Bot durumu gerçek zamanlı güncelleniyor
- ✅ Monitoring başlatma/durdurma entegrasyonu

## 🚀 Kullanım

### Backend (Bot) Başlatma

```bash
# Ana dizinde
npm install
npm run dev
```

Bot başladığında:
- API Server: `http://localhost:3001` üzerinde çalışır
- WebSocket: `ws://localhost:3001` üzerinde dinler
- Bot DURDURULMUŞ durumda başlar
- Dashboard'dan başlatmanız gerekir

### Frontend (Dashboard) Başlatma

```bash
# Dashboard dizininde
cd dashboard
npm install
npm run dev
```

Dashboard:
- `http://localhost:5173` üzerinde açılır
- Otomatik olarak backend'e bağlanır
- Real-time güncellemeler alır

## 📊 Dashboard Özellikleri

### Status Card
- **Bot Status**: Active/Inactive (gerçek durum)
- **Target Wallet**: ENV'den alınan gerçek adres
- **My Wallet**: ENV'den alınan gerçek adres
- **Poll Rate**: 200ms (INSTANT COPY mode)
- **Uptime**: Bot çalışma süresi
- **Last Check**: Son kontrol zamanı

### Risk Metrics
- **Current Balance**: Gerçek cüzdan bakiyesi
- **Max Position Size**: Risk config'den
- **Total Exposure**: Tüm açık pozisyonların toplamı
- **Daily Loss**: Günlük kayıp/kazanç
- **Risk Level**: Dinamik hesaplanan risk seviyesi (LOW/MEDIUM/HIGH)

### Trade History
- **Market**: Trade yapılan market
- **Side**: BUY/SELL
- **Size**: Trade miktarı (USDC)
- **Price**: Trade fiyatı
- **Status**: COPIED/FAILED
- **Latency**: Detection'dan execution'a kadar geçen süre

### Live Logs
- **INFO**: Genel bilgilendirme mesajları
- **SUCCESS**: Başarılı işlemler
- **WARNING**: Uyarılar
- **ERROR**: Hatalar
- Otomatik scroll to bottom
- Son 200 log kaydı

## 🔄 Veri Akışı

```
Target User Trade
     ↓
Real-time Monitor (200ms polling)
     ↓
Trade Detection
     ↓
Log to Dashboard (WebSocket) → "Trade detected"
     ↓
Risk Checks
     ↓
Trade Executor
     ↓
PostOrder (BUY/SELL/MERGE)
     ↓
Update Dashboard (WebSocket) → "COPIED" or "FAILED"
     ↓
Update Risk Metrics
```

## 🎛️ Bot Kontrolü

### Start Bot
1. Dashboard'da "Start Bot" butonuna tıklayın
2. Real-time monitoring başlar (200ms polling)
3. Status ACTIVE olur
4. Trade'ler otomatik copy edilmeye başlar

### Stop Bot
1. Dashboard'da "Stop Bot" butonuna tıklayın
2. Real-time monitoring durur
3. Status INACTIVE olur
4. Yeni trade'ler detect edilmez

## 📝 API Endpoints

### GET `/api/status`
Bot durumu, uptime, wallet adresleri

### GET `/api/risk`
Risk metrikleri, balance, exposure

### GET `/api/logs`
Son loglar (limit ile)

### GET `/api/trades`
Son trade'ler (limit ile)

### POST `/api/bot/toggle`
Bot'u başlat/durdur

## 🔌 WebSocket Events

### Gelen Events
- `log`: Yeni log mesajı
- `logs`: Tüm loglar (initial)
- `trade`: Yeni trade
- `trades`: Tüm trade'ler (initial)

## 🎨 Visualizasyon

Dashboard tam entegre ve hiç mockup veri yok:
- ✅ Tüm veriler gerçek zamanlı backend'den
- ✅ WebSocket ile instant updates
- ✅ Risk metrikleri canlı hesaplanıyor
- ✅ Trade history gerçek copy işlemlerini gösteriyor
- ✅ Logs botun tüm aktivitelerini gösteriyor

## 🛠️ Geliştirme Notları

### Eklenen Özellikler
1. `addTrade()` fonksiyonu - Trade'leri dashboard'a broadcast eder
2. `addLog()` fonksiyonu - Log mesajlarını broadcast eder
3. Risk Manager entegrasyonu - Gerçek risk metrikleri
4. Bot toggle - Dashboard'dan kontrol
5. Real-time monitoring control

### Değiştirilen Dosyalar
- `src/api/server.ts` - Risk metrics, bot control
- `src/services/tradeExecutor.ts` - Trade status reporting
- `src/utils/postOrder.ts` - Success/failure tracking
- `src/services/realtimeMonitor.ts` - Trade detection logging
- `src/index.ts` - Bot başlangıç kontrolü
- `dashboard/src/hooks/useApi.ts` - Mockup veri kaldırma

## ⚠️ Önemli Notlar

1. **Environment Variables**: `.env` dosyanızı doğru ayarladığınızdan emin olun
2. **MongoDB**: Database connection çalışıyor olmalı
3. **Ports**: 3001 (API) ve 5173 (Dashboard) portları açık olmalı
4. **WebSocket**: CORS ayarları düzgün yapılandırıldı
5. **Initial State**: Bot başlangıçta STOPPED - manuel başlatın

## 🐛 Troubleshooting

### Dashboard veri göstermiyor
- Backend'in çalıştığından emin olun
- Browser console'da WebSocket bağlantısını kontrol edin
- API endpoint'lerinin yanıt verdiğini test edin

### Bot trade copy etmiyor
- Bot durumunun ACTIVE olduğunu kontrol edin
- Risk limitlerinizi kontrol edin
- Logs'da error mesajlarına bakın

### WebSocket bağlanmıyor
- CORS ayarlarını kontrol edin
- Port 3001'in açık olduğunu kontrol edin
- Firewall ayarlarını kontrol edin
