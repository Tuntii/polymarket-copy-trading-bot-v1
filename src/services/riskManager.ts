import { RiskConfig, getRiskConfig } from '../config/riskConfig';
import { UserPositionInterface } from '../interfaces/User';
import getMyBalance from '../utils/getMyBalance';
import fetchData from '../utils/fetchData';
import { ENV } from '../config/env';

const PROXY_WALLET = ENV.PROXY_WALLET;

interface RiskCheckResult {
    allowed: boolean;
    reason?: string;
    adjustedAmount?: number;
}

interface TradeStats {
    dailyPnL: number;
    tradesLastHour: number;
    tradesToday: number;
    lastTradeTime: number;
    totalExposure: number;
}

// In-memory trade statistics (resets on restart)
const tradeStats: TradeStats = {
    dailyPnL: 0,
    tradesLastHour: 0,
    tradesToday: 0,
    lastTradeTime: 0,
    totalExposure: 0,
};

const tradeTimestamps: number[] = [];

class RiskManager {
    private config: RiskConfig;

    constructor() {
        this.config = getRiskConfig();
    }

    /**
     * Tüm risk kontrollerini çalıştır
     */
    async performFullRiskCheck(
        side: 'BUY' | 'SELL',
        amount: number,
        currentPrice: number,
        originalPrice: number,
        conditionId: string,
        title?: string // Market başlığı - zaman kontrolü için
    ): Promise<RiskCheckResult> {
        const checks = [
            () => this.checkMarketResolved(currentPrice),  // Önce market çözülmüş mü kontrol et
            () => title ? this.checkMarketTimeRemaining(title, 0.5) : { allowed: true }, // 30 saniye kalan zaman kontrolü (INSTANT COPY)
            () => this.checkMinTradeAmount(amount),
            () => this.checkMaxPositionSize(amount),
            () => this.checkDailyLossLimit(),
            () => this.checkTradeFrequency(),
            () => this.checkSlippage(currentPrice, originalPrice),
            () => this.checkPriceDifference(currentPrice, originalPrice),
            async () => await this.checkBalanceProtection(amount, side),
            async () => await this.checkTotalExposure(amount, side),
        ];

        for (const check of checks) {
            const result = await check();
            if (!result.allowed) {
                console.log(`❌ Risk Check Failed: ${result.reason}`);
                return result;
            }
        }

        // Adjust amount based on copy ratio and balance
        const adjustedResult = await this.adjustTradeAmount(amount, side);
        
        console.log(`✅ All risk checks passed. Amount: ${amount} → ${adjustedResult.adjustedAmount}`);
        return adjustedResult;
    }

    /**
     * Market başlığından bitiş zamanını parse et ve kalan dakikayı hesapla
     * Örnek: "Bitcoin Up or Down - January 10, 6:30PM-6:45PM ET"
     */
    parseMarketEndTime(title: string): { minutesRemaining: number; endTime: string } | null {
        try {
            // Pattern: "HH:MMAM/PM-HH:MMAM/PM ET" formatını yakala
            const timePattern = /(\d{1,2}):(\d{2})(AM|PM)-(\d{1,2}):(\d{2})(AM|PM)\s*ET/i;
            const match = title.match(timePattern);
            
            if (!match) {
                return null; // Bu format değilse normal trade
            }

            const [_, startHour, startMin, startAmPm, endHour, endMin, endAmPm] = match;
            
            // Bitiş saatini 24 saat formatına çevir
            let endHour24 = parseInt(endHour);
            if (endAmPm.toUpperCase() === 'PM' && endHour24 !== 12) {
                endHour24 += 12;
            } else if (endAmPm.toUpperCase() === 'AM' && endHour24 === 12) {
                endHour24 = 0;
            }

            // Şu anki zamanı ET (Eastern Time) olarak al
            // ET = UTC-5 (EST) veya UTC-4 (EDT)
            const now = new Date();
            const utcHours = now.getUTCHours();
            const utcMinutes = now.getUTCMinutes();
            
            // EST (UTC-5) kullan - kış saati
            const etHours = (utcHours - 5 + 24) % 24;
            const etMinutes = utcMinutes;
            
            // Şu anki ET zamanı dakika cinsinden
            const currentMinutesET = etHours * 60 + etMinutes;
            
            // Market bitiş zamanı dakika cinsinden
            const endMinutesET = endHour24 * 60 + parseInt(endMin);
            
            // Kalan dakika
            let minutesRemaining = endMinutesET - currentMinutesET;
            
            // Gece yarısı geçişi
            if (minutesRemaining < -60) {
                minutesRemaining += 24 * 60;
            }
            
            const endTimeStr = `${endHour}:${endMin}${endAmPm} ET`;
            
            return { minutesRemaining, endTime: endTimeStr };
        } catch (error) {
            console.error('Error parsing market time:', error);
            return null;
        }
    }

    /**
     * Market'te yeterli zaman kaldı mı kontrolü (minimum 10 dakika)
     */
    checkMarketTimeRemaining(title: string, minMinutes: number = 10): RiskCheckResult {
        const timeInfo = this.parseMarketEndTime(title);
        
        if (!timeInfo) {
            // Zaman formatı bulunamadıysa normal trade'e izin ver
            return { allowed: true };
        }

        if (timeInfo.minutesRemaining < minMinutes) {
            return {
                allowed: false,
                reason: `⏰ Market ends in ${timeInfo.minutesRemaining.toFixed(0)} min (${timeInfo.endTime}). Need ${minMinutes}+ min remaining.`,
            };
        }

        console.log(`✅ Market time OK: ${timeInfo.minutesRemaining.toFixed(0)} min remaining until ${timeInfo.endTime}`);
        return { allowed: true };
    }

    /**
     * Market çözülmüş mü kontrolü - SADECE TAM ÇÖZÜLMÜŞ MARKETLER ATLANIR
     * AGRESİF MOD: 0.999 ve 0.001 dışında her şeye izin ver
     */
    checkMarketResolved(currentPrice: number): RiskCheckResult {
        // Sadece tam 1.00 veya 0.00'a çok yakın olanları atla
        if (currentPrice >= 0.999 || currentPrice <= 0.001) {
            return {
                allowed: false,
                reason: `Market fully resolved (price: ${currentPrice}). Cannot trade.`,
            };
        }
        // 0.99 civarı bile olsa trade'e izin ver - hızlı marketler için
        if (currentPrice >= 0.98) {
            console.log(`⚠️ Warning: High price (${currentPrice}) - market may resolve soon`);
        }
        return { allowed: true };
    }

    /**
     * Minimum trade miktarı kontrolü
     */
    checkMinTradeAmount(amount: number): RiskCheckResult {
        if (amount < this.config.minTradeAmountUSDC) {
            return {
                allowed: false,
                reason: `Trade amount ($${amount}) is below minimum ($${this.config.minTradeAmountUSDC})`,
            };
        }
        return { allowed: true };
    }

    /**
     * Maksimum pozisyon boyutu kontrolü
     */
    checkMaxPositionSize(amount: number): RiskCheckResult {
        if (amount > this.config.maxPositionSizeUSDC) {
            return {
                allowed: true,
                adjustedAmount: this.config.maxPositionSizeUSDC,
                reason: `Amount capped to max position size: $${this.config.maxPositionSizeUSDC}`,
            };
        }
        return { allowed: true, adjustedAmount: amount };
    }

    /**
     * Günlük kayıp limiti kontrolü
     */
    checkDailyLossLimit(): RiskCheckResult {
        if (tradeStats.dailyPnL <= -this.config.maxDailyLossUSDC) {
            return {
                allowed: false,
                reason: `Daily loss limit reached: $${Math.abs(tradeStats.dailyPnL)} / $${this.config.maxDailyLossUSDC}`,
            };
        }
        return { allowed: true };
    }

    /**
     * Trade frekansı kontrolü
     */
    checkTradeFrequency(): RiskCheckResult {
        const now = Date.now();
        
        // Minimum süre kontrolü
        if (now - tradeStats.lastTradeTime < this.config.minTimeBetweenTradesMs) {
            const waitTime = this.config.minTimeBetweenTradesMs - (now - tradeStats.lastTradeTime);
            return {
                allowed: false,
                reason: `Too soon since last trade. Wait ${waitTime}ms`,
            };
        }

        // Son 1 saatteki trade sayısını hesapla
        const oneHourAgo = now - 3600000;
        const tradesLastHour = tradeTimestamps.filter(t => t > oneHourAgo).length;
        
        if (tradesLastHour >= this.config.maxTradesPerHour) {
            return {
                allowed: false,
                reason: `Hourly trade limit reached: ${tradesLastHour}/${this.config.maxTradesPerHour}`,
            };
        }

        // Günlük trade sayısı
        const startOfDay = new Date().setHours(0, 0, 0, 0);
        const tradesToday = tradeTimestamps.filter(t => t > startOfDay).length;
        
        if (tradesToday >= this.config.maxTradesPerDay) {
            return {
                allowed: false,
                reason: `Daily trade limit reached: ${tradesToday}/${this.config.maxTradesPerDay}`,
            };
        }

        return { allowed: true };
    }

    /**
     * Slippage kontrolü - POLYMARKET İÇİN OPTİMİZE
     * Polymarket'te fiyatlar 0-1 arası olduğu için mutlak fark kullanıyoruz
     * Örnek: 0.50 -> 0.55 = 5% slippage (0.05 * 100)
     */
    checkSlippage(currentPrice: number, originalPrice: number): RiskCheckResult {
        // Mutlak fiyat farkı (Polymarket için)
        const slippage = Math.abs(currentPrice - originalPrice) * 100;
        
        if (slippage > this.config.maxSlippagePercent) {
            return {
                allowed: false,
                reason: `Slippage too high: ${slippage.toFixed(2)}% (${originalPrice.toFixed(3)} → ${currentPrice.toFixed(3)}) > ${this.config.maxSlippagePercent}%`,
            };
        }
        return { allowed: true };
    }

    /**
     * Fiyat farkı kontrolü (copy trading için) - POLYMARKET İÇİN OPTİMİZE
     * Polymarket'te fiyatlar 0-1 arası olduğu için mutlak fark kullanıyoruz
     */
    checkPriceDifference(currentPrice: number, originalPrice: number): RiskCheckResult {
        // Mutlak fiyat farkı (Polymarket için)
        const priceDiff = Math.abs(currentPrice - originalPrice) * 100;
        
        if (priceDiff > this.config.skipIfPriceChangedPercent) {
            return {
                allowed: false,
                reason: `Price changed too much: ${priceDiff.toFixed(2)}% (${originalPrice.toFixed(3)} → ${currentPrice.toFixed(3)}) > ${this.config.skipIfPriceChangedPercent}%`,
            };
        }
        return { allowed: true };
    }

    /**
     * Bakiye koruma kontrolü
     */
    async checkBalanceProtection(amount: number, side: 'BUY' | 'SELL'): Promise<RiskCheckResult> {
        if (side === 'SELL') {
            return { allowed: true }; // Satışta bakiye kontrolü gerekmiyor
        }

        try {
            const balance = await getMyBalance(PROXY_WALLET);
            const availableBalance = balance - this.config.minBalanceToKeepUSDC;
            
            if (availableBalance <= 0) {
                return {
                    allowed: false,
                    reason: `Insufficient balance. Current: $${balance}, Minimum to keep: $${this.config.minBalanceToKeepUSDC}`,
                };
            }

            const maxUsable = balance * (this.config.maxBalanceUsagePercent / 100);
            
            if (amount > maxUsable) {
                return {
                    allowed: true,
                    adjustedAmount: Math.min(maxUsable, availableBalance),
                    reason: `Amount adjusted to ${this.config.maxBalanceUsagePercent}% of balance`,
                };
            }

            if (amount > availableBalance) {
                return {
                    allowed: true,
                    adjustedAmount: availableBalance,
                    reason: `Amount adjusted to available balance: $${availableBalance}`,
                };
            }

            return { allowed: true };
        } catch (error) {
            console.error('Error checking balance:', error);
            return {
                allowed: false,
                reason: 'Failed to check balance',
            };
        }
    }

    /**
     * Toplam exposure kontrolü
     */
    async checkTotalExposure(amount: number, side: 'BUY' | 'SELL'): Promise<RiskCheckResult> {
        if (side === 'SELL') {
            return { allowed: true };
        }

        try {
            const positions: UserPositionInterface[] = await fetchData(
                `https://data-api.polymarket.com/positions?user=${PROXY_WALLET}`
            );
            
            const totalExposure = positions.reduce((sum, pos) => sum + (pos.currentValue || 0), 0);
            
            if (totalExposure + amount > this.config.maxTotalExposureUSDC) {
                const maxAllowed = Math.max(0, this.config.maxTotalExposureUSDC - totalExposure);
                
                if (maxAllowed <= this.config.minTradeAmountUSDC) {
                    return {
                        allowed: false,
                        reason: `Total exposure limit would be exceeded: $${totalExposure} + $${amount} > $${this.config.maxTotalExposureUSDC}`,
                    };
                }
                
                return {
                    allowed: true,
                    adjustedAmount: maxAllowed,
                    reason: `Amount reduced to stay within exposure limit: $${maxAllowed}`,
                };
            }

            return { allowed: true };
        } catch (error) {
            console.error('Error checking total exposure:', error);
            return { allowed: true }; // Hata durumunda devam et
        }
    }

    /**
     * Trade miktarını ayarla (copy ratio ve diğer faktörler)
     */
    async adjustTradeAmount(amount: number, side: 'BUY' | 'SELL'): Promise<RiskCheckResult> {
        let adjustedAmount = amount * (this.config.copyRatioPercent / 100);
        
        // Minimum kontrolü
        if (adjustedAmount < this.config.minTradeAmountUSDC) {
            return {
                allowed: false,
                reason: `Adjusted amount ($${adjustedAmount.toFixed(2)}) below minimum after applying copy ratio`,
            };
        }

        // Maksimum pozisyon kontrolü
        adjustedAmount = Math.min(adjustedAmount, this.config.maxPositionSizeUSDC);

        // Bakiye kontrolü (sadece alım için)
        if (side === 'BUY') {
            try {
                const balance = await getMyBalance(PROXY_WALLET);
                const availableBalance = balance - this.config.minBalanceToKeepUSDC;
                const maxUsable = balance * (this.config.maxBalanceUsagePercent / 100);
                
                adjustedAmount = Math.min(adjustedAmount, availableBalance, maxUsable);
                
                if (adjustedAmount < this.config.minTradeAmountUSDC) {
                    return {
                        allowed: false,
                        reason: `Insufficient funds after adjustments`,
                    };
                }
            } catch (error) {
                console.error('Error adjusting trade amount:', error);
            }
        }

        return {
            allowed: true,
            adjustedAmount: parseFloat(adjustedAmount.toFixed(2)),
        };
    }

    /**
     * Stop-loss kontrolü (mevcut pozisyon için)
     */
    async checkStopLoss(position: UserPositionInterface): Promise<boolean> {
        if (!position.percentPnl) return false;
        
        if (position.percentPnl <= -this.config.stopLossPercent) {
            console.log(`🛑 Stop-loss triggered for ${position.title}: ${position.percentPnl}%`);
            return true;
        }
        return false;
    }

    /**
     * Take-profit kontrolü (mevcut pozisyon için)
     */
    async checkTakeProfit(position: UserPositionInterface): Promise<boolean> {
        if (!position.percentPnl) return false;
        
        if (position.percentPnl >= this.config.takeProfitPercent) {
            console.log(`🎯 Take-profit triggered for ${position.title}: ${position.percentPnl}%`);
            return true;
        }
        return false;
    }

    /**
     * Trade tamamlandıktan sonra istatistikleri güncelle
     */
    recordTrade(pnl: number = 0): void {
        const now = Date.now();
        tradeStats.lastTradeTime = now;
        tradeStats.dailyPnL += pnl;
        tradeTimestamps.push(now);

        // Eski timestamp'leri temizle (24 saatten eski)
        const oneDayAgo = now - 86400000;
        while (tradeTimestamps.length > 0 && tradeTimestamps[0] < oneDayAgo) {
            tradeTimestamps.shift();
        }
    }

    /**
     * Günlük istatistikleri sıfırla
     */
    resetDailyStats(): void {
        tradeStats.dailyPnL = 0;
        tradeStats.tradesToday = 0;
        console.log('📊 Daily stats reset');
    }

    /**
     * Mevcut risk durumunu getir
     */
    async getRiskStatus(): Promise<{
        config: RiskConfig;
        stats: TradeStats;
        balance: number;
        positions: UserPositionInterface[];
    }> {
        const balance = await getMyBalance(PROXY_WALLET);
        const positions: UserPositionInterface[] = await fetchData(
            `https://data-api.polymarket.com/positions?user=${PROXY_WALLET}`
        );
        
        const totalExposure = positions.reduce((sum, pos) => sum + (pos.currentValue || 0), 0);
        tradeStats.totalExposure = totalExposure;

        return {
            config: this.config,
            stats: { ...tradeStats },
            balance,
            positions,
        };
    }

    /**
     * Config'i runtime'da güncelle
     */
    updateConfig(newConfig: Partial<RiskConfig>): void {
        this.config = { ...this.config, ...newConfig };
        console.log('⚙️ Risk config updated:', newConfig);
    }
}

// Singleton instance
const riskManager = new RiskManager();

export default riskManager;
export { RiskCheckResult, TradeStats };
