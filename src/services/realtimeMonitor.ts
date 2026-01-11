/**
 * REAL-TIME TRADE MONITORING
 * Polymarket Data API'sinden gerçek zamanlı trade'leri takip eder
 * Polling yerine sürekli aktif bağlantı ile minimum gecikme sağlar
 */

import { ENV } from '../config/env';
import { UserActivityInterface } from '../interfaces/User';
import { getUserActivityModel } from '../models/userHistory';
import fetchData from '../utils/fetchData';

const USER_ADDRESS = ENV.USER_ADDRESS;
const UserActivity = getUserActivityModel(USER_ADDRESS);

// Son işlem timestamp'i
let lastTradeTimestamp: number = 0;
let isMonitoring: boolean = false;
let botStartTime: number = 0; // Bot başlangıç zamanı

// Trade callback fonksiyonu
type TradeCallback = (trade: UserActivityInterface) => void;
let tradeCallback: TradeCallback | null = null;

/**
 * Gerçek zamanlı monitoring başlat
 * Her 200ms'de bir API'yi kontrol eder (5 req/second)
 */
export const startRealtimeMonitoring = (callback: TradeCallback): void => {
    if (isMonitoring) {
        console.log('⚠️ Real-time monitoring already running');
        return;
    }

    tradeCallback = callback;
    isMonitoring = true;
    
    // Bot başlangıç zamanını kaydet
    botStartTime = Math.floor(Date.now() / 1000);

    console.log('\n⚡ REAL-TIME MONITORING STARTED');
    console.log('   🎯 Target: ' + USER_ADDRESS);
    console.log('   ⏱️  Poll Rate: 200ms (5 req/sec)');
    console.log('   🚀 Mode: INSTANT COPY');
    console.log(`   📅 Start Time: ${new Date(botStartTime * 1000).toISOString()}\n`);

    // Son trade timestamp'ini bot başlangıç zamanına ayarla
    lastTradeTimestamp = botStartTime;
    console.log(`✅ Only processing trades AFTER bot start time\n`);

    // Monitoring loop başlat
    startMonitoringLoop();
};

/**
 * Son trade timestamp'ini yükle
 */
const initializeLastTrade = async (): Promise<void> => {
    try {
        const latestTrade = await UserActivity.findOne()
            .sort({ timestamp: -1 })
            .exec();
        
        if (latestTrade) {
            lastTradeTimestamp = (latestTrade as UserActivityInterface).timestamp || 0;
            console.log(`📚 Last trade loaded: ${new Date(lastTradeTimestamp * 1000).toISOString()}`);
        } else {
            lastTradeTimestamp = Math.floor(Date.now() / 1000) - 900; // Son 15 dakika
            console.log(`📚 No previous trades, starting from 15 minutes ago`);
        }
    } catch (error) {
        console.error('❌ Error loading last trade:', error);
        lastTradeTimestamp = Math.floor(Date.now() / 1000) - 900;
    }
};

/**
 * Monitoring döngüsü
 */
const startMonitoringLoop = (): void => {
    const pollInterval = 200; // 200ms = 5 req/sec

    const checkForNewTrades = async () => {
        if (!isMonitoring) return;

        try {
            // API'den son trade'leri çek
            const activities: UserActivityInterface[] = await fetchData(
                `https://data-api.polymarket.com/activity?user=${USER_ADDRESS}&limit=20`
            );

            if (!activities || activities.length === 0) {
                setTimeout(checkForNewTrades, pollInterval);
                return;
            }

            // Sadece TRADE tipindeki yeni aktiviteleri al
            // VE sadece bot başladıktan SONRA oluşanları
            const newTrades = activities.filter(activity => 
                activity.type === 'TRADE' && 
                activity.timestamp > lastTradeTimestamp &&
                activity.timestamp > botStartTime // Bot başladıktan sonra
            );

            if (newTrades.length > 0) {
                // Timestamp'e göre sırala (eski -> yeni)
                newTrades.sort((a, b) => a.timestamp - b.timestamp);

                for (const trade of newTrades) {
                    console.log('\n⚡ INSTANT TRADE DETECTED! ⚡');
                    console.log(`   ⏱️  Latency: ~${Date.now() / 1000 - trade.timestamp}s`);
                    console.log(`   💰 ${trade.side} $${trade.usdcSize?.toFixed(2)} @ ${trade.price}`);
                    console.log(`   📊 ${trade.title}\n`);

                    // Trade'i kaydet
                    await saveTradeToDb(trade);

                    // Callback'i çağır (instant copy için)
                    if (tradeCallback) {
                        tradeCallback(trade);
                    }

                    // Timestamp güncelle
                    lastTradeTimestamp = trade.timestamp;
                }
            }

        } catch (error) {
            console.error('❌ Monitoring error:', error);
        }

        // Bir sonraki kontrolü planla
        setTimeout(checkForNewTrades, pollInterval);
    };

    // İlk kontrolü başlat
    checkForNewTrades();
};

/**
 * Trade'i database'e kaydet
 */
const saveTradeToDb = async (trade: UserActivityInterface): Promise<void> => {
    try {
        // Daha önce kaydedilmiş mi kontrol et
        const existing = await UserActivity.findOne({
            transactionHash: trade.transactionHash,
        }).exec();

        if (existing) {
            return; // Zaten var
        }

        // Yeni trade olarak kaydet
        const newActivity = new UserActivity({
            ...trade,
            bot: false,
            botExcutedTime: 0,
        });

        await newActivity.save();
    } catch (error) {
        console.error('❌ Error saving trade to DB:', error);
    }
};

/**
 * Monitoring'i durdur
 */
export const stopRealtimeMonitoring = (): void => {
    isMonitoring = false;
    tradeCallback = null;
    console.log('\n⛔ Real-time monitoring stopped\n');
};

/**
 * Monitoring durumunu al
 */
export const isMonitoringActive = (): boolean => {
    return isMonitoring;
};
