export interface RiskConfig {
    // Position Limits
    maxPositionSizeUSDC: number;        // Tek pozisyon için maksimum USDC
    maxTotalExposureUSDC: number;       // Toplam açık pozisyon limiti
    minTradeAmountUSDC: number;         // Minimum trade miktarı
    
    // Loss Limits
    maxDailyLossUSDC: number;           // Günlük maksimum kayıp
    maxDailyLossPercent: number;        // Günlük maksimum kayıp yüzdesi
    stopLossPercent: number;            // Stop-loss yüzdesi (pozisyon bazlı)
    
    // Profit Targets
    takeProfitPercent: number;          // Take-profit yüzdesi
    
    // Slippage & Price Protection
    maxSlippagePercent: number;         // Maksimum kayma toleransı
    maxPriceDifferencePercent: number;  // Hedef fiyattan maksimum sapma
    
    // Trade Frequency
    minTimeBetweenTradesMs: number;     // İşlemler arası minimum süre (ms)
    maxTradesPerHour: number;           // Saatlik maksimum işlem sayısı
    maxTradesPerDay: number;            // Günlük maksimum işlem sayısı
    
    // Balance Protection
    minBalanceToKeepUSDC: number;       // Hesapta tutulacak minimum bakiye
    maxBalanceUsagePercent: number;     // Bakiyenin maksimum kullanım yüzdesi
    
    // Copy Trading Specific
    copyRatioPercent: number;           // Hedef kullanıcının işleminin kaçını kopyala
    skipIfPriceChangedPercent: number;  // Fiyat bu kadar değiştiyse işlemi atla
}

// Default risk configuration - $10 bakiye için MAKSİMUM TRADE optimize edildi
export const DEFAULT_RISK_CONFIG: RiskConfig = {
    // Position Limits - KÜÇÜK POZİSYONLAR = FAZLA TRADE
    maxPositionSizeUSDC: 1.5,           // Tek pozisyon max $1.50 (daha fazla trade için küçük tut)
    maxTotalExposureUSDC: 10,           // Toplam açık pozisyon max $10
    minTradeAmountUSDC: 0.5,            // Minimum $0.50 trade (Polymarket minimum)
    
    // Loss Limits - AGRESİF
    maxDailyLossUSDC: 5,                // Günlük max kayıp $5 (paranın yarısı - agresif)
    maxDailyLossPercent: 50,            // Günlük max %50 kayıp (agresif trading)
    stopLossPercent: 40,                // Pozisyon bazlı %40 stop-loss (geniş)
    
    // Profit Targets
    takeProfitPercent: 30,              // Pozisyon bazlı %30 kar al (hızlı çık)
    
    // Slippage & Price Protection - ÇOK TOLERANSLI (AGRESİF)
    maxSlippagePercent: 50,             // %50 kayma toleransı (fiyat ne olursa olsun gir)
    maxPriceDifferencePercent: 90,      // Hedef fiyattan max %90 sapma (neredeyse sınırsız)
    
    // Trade Frequency - MAKSİMUM
    minTimeBetweenTradesMs: 500,        // İşlemler arası min 0.5 saniye (çok hızlı)
    maxTradesPerHour: 100,              // Saatte max 100 işlem
    maxTradesPerDay: 500,               // Günde max 500 işlem
    
    // Balance Protection - MİNİMAL
    minBalanceToKeepUSDC: 0.5,          // Sadece $0.50 kalsın (agresif)
    maxBalanceUsagePercent: 95,         // Bakiyenin %95'i kullanılabilir
    
    // Copy Trading Specific - AGRESİF
    copyRatioPercent: 100,              // Hedef işlemi kopyala (miktar otomatik $1.50'ye scale)
    skipIfPriceChangedPercent: 95,      // Fiyat %95 değişse bile gir (neredeyse her zaman kopyala)
};

// Runtime'da ayarları özelleştirmek için
let customConfig: Partial<RiskConfig> = {};

export const getRiskConfig = (): RiskConfig => {
    return { ...DEFAULT_RISK_CONFIG, ...customConfig };
};

export const updateRiskConfig = (updates: Partial<RiskConfig>): void => {
    customConfig = { ...customConfig, ...updates };
    console.log('⚙️ Risk config updated:', updates);
};
