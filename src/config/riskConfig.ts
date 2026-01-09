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

// Default risk configuration - sabit değerler, .env'den özelleştirilebilir
export const DEFAULT_RISK_CONFIG: RiskConfig = {
    // Position Limits
    maxPositionSizeUSDC: 100,
    maxTotalExposureUSDC: 500,
    minTradeAmountUSDC: 1,
    
    // Loss Limits
    maxDailyLossUSDC: 50,
    maxDailyLossPercent: 10,
    stopLossPercent: 20,
    
    // Profit Targets
    takeProfitPercent: 50,
    
    // Slippage & Price Protection
    maxSlippagePercent: 2,
    maxPriceDifferencePercent: 5,
    
    // Trade Frequency
    minTimeBetweenTradesMs: 5000,
    maxTradesPerHour: 20,
    maxTradesPerDay: 100,
    
    // Balance Protection
    minBalanceToKeepUSDC: 10,
    maxBalanceUsagePercent: 80,
    
    // Copy Trading Specific
    copyRatioPercent: 100,
    skipIfPriceChangedPercent: 10,
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
