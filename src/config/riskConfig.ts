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

// Default risk configuration - $30 bakiye için optimize edildi
export const DEFAULT_RISK_CONFIG: RiskConfig = {
    // Position Limits
    maxPositionSizeUSDC: 10,            // Tek pozisyon max $10 (bakiyenin %33'ü)
    maxTotalExposureUSDC: 25,           // Toplam açık pozisyon max $25
    minTradeAmountUSDC: 0.1,            // Minimum $0.10 trade (küçük işlemleri de kopyala)
    
    // Loss Limits
    maxDailyLossUSDC: 6,                // Günlük max kayıp $6 (bakiyenin %20'si)
    maxDailyLossPercent: 20,            // Günlük max %20 kayıp
    stopLossPercent: 25,                // Pozisyon bazlı %25 stop-loss
    
    // Profit Targets
    takeProfitPercent: 40,              // Pozisyon bazlı %40 kar al
    
    // Slippage & Price Protection
    maxSlippagePercent: 5,              // %5 kayma toleransı (daha toleranslı)
    maxPriceDifferencePercent: 10,      // Hedef fiyattan max %10 sapma
    
    // Trade Frequency
    minTimeBetweenTradesMs: 3000,       // İşlemler arası min 3 saniye
    maxTradesPerHour: 15,               // Saatte max 15 işlem
    maxTradesPerDay: 50,                // Günde max 50 işlem
    
    // Balance Protection
    minBalanceToKeepUSDC: 3,            // Her zaman $3 kalsın (acil durum için)
    maxBalanceUsagePercent: 90,         // Bakiyenin max %90'ı kullanılabilir
    
    // Copy Trading Specific
    copyRatioPercent: 100,              // Hedef kullanıcının işlemini %100 kopyala (miktar otomatik ayarlanır)
    skipIfPriceChangedPercent: 15,      // Fiyat %15'ten fazla değiştiyse atla
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
