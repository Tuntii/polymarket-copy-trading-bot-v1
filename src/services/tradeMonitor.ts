import moment from 'moment';
import { ENV } from '../config/env';
import { UserActivityInterface, UserPositionInterface } from '../interfaces/User';
import { getUserActivityModel, getUserPositionModel } from '../models/userHistory';
import fetchData from '../utils/fetchData';
import riskManager from './riskManager';

const USER_ADDRESS = ENV.USER_ADDRESS;
const TOO_OLD_TIMESTAMP = ENV.TOO_OLD_TIMESTAMP;
const FETCH_INTERVAL = ENV.FETCH_INTERVAL;
const PROXY_WALLET = ENV.PROXY_WALLET;

if (!USER_ADDRESS) {
    throw new Error('USER_ADDRESS is not defined');
}

const UserActivity = getUserActivityModel(USER_ADDRESS);
const UserPosition = getUserPositionModel(USER_ADDRESS);

// Takip edilen son işlem timestamp'i (milisaniye cinsinden)
let lastFetchedTimestamp: number = 0;
let isFirstRun: boolean = true;

/**
 * Başlangıçta mevcut işlemleri yükle
 */
const init = async () => {
    try {
        // MongoDB'den en son işlemi bul
        const latestTrade = await UserActivity.findOne()
            .sort({ timestamp: -1 })
            .exec();
        
        if (latestTrade) {
            // DB'de saniye cinsinden saklanıyor, milisaniyeye çevir
            const dbTimestamp = (latestTrade as UserActivityInterface).timestamp || 0;
            lastFetchedTimestamp = dbTimestamp * 1000;
            console.log(`📚 Loaded last trade timestamp: ${moment(lastFetchedTimestamp).format('YYYY-MM-DD HH:mm:ss')}`);
        }
        
        // İlk çalışmada geçmiş işlemleri işleme
        isFirstRun = true;
        console.log('✅ Trade monitor initialized');
    } catch (error) {
        console.error('❌ Error initializing trade monitor:', error);
    }
};

/**
 * Hedef kullanıcının aktivitelerini API'den çek
 */
const fetchUserActivities = async (): Promise<UserActivityInterface[]> => {
    try {
        const activities: UserActivityInterface[] = await fetchData(
            `https://data-api.polymarket.com/activity?user=${USER_ADDRESS}&limit=50`
        );
        return activities || [];
    } catch (error) {
        console.error('❌ Error fetching user activities:', error);
        return [];
    }
};

/**
 * Hedef kullanıcının pozisyonlarını çek
 */
const fetchUserPositions = async (): Promise<UserPositionInterface[]> => {
    try {
        const positions: UserPositionInterface[] = await fetchData(
            `https://data-api.polymarket.com/positions?user=${USER_ADDRESS}`
        );
        return positions || [];
    } catch (error) {
        console.error('❌ Error fetching user positions:', error);
        return [];
    }
};

/**
 * Yeni işlemleri filtrele ve kaydet
 */
const processNewTrades = async (activities: UserActivityInterface[]): Promise<number> => {
    let newTradesCount = 0;
    const now = Date.now();
    const tooOldThreshold = now - (TOO_OLD_TIMESTAMP * 60 * 1000); // TOO_OLD_TIMESTAMP dakika öncesi

    for (const activity of activities) {
        // Sadece TRADE tipindeki işlemleri al
        if (activity.type !== 'TRADE') {
            continue;
        }

        // Timestamp kontrolü - API saniye döndürüyor, milisaniyeye çevir
        const activityTimestamp = (activity.timestamp || 0) * 1000;
        
        // Çok eski işlemleri atla (sessizce)
        if (activityTimestamp < tooOldThreshold) {
            continue;
        }

        // Zaten işlenmiş işlemleri atla
        if (activityTimestamp <= lastFetchedTimestamp) {
            continue;
        }

        // İlk çalışmada geçmiş işlemleri sadece kaydet, kopyalama
        if (isFirstRun) {
            await saveActivityToDB(activity, true); // bot: true olarak kaydet
            continue;
        }

        // Daha önce kaydedilmiş mi kontrol et
        const existingTrade = await UserActivity.findOne({
            transactionHash: activity.transactionHash,
        }).exec();

        if (existingTrade) {
            continue;
        }

        // Yeni işlemi kaydet
        await saveActivityToDB(activity, false);
        newTradesCount++;

        console.log(`\n🔔 NEW TRADE DETECTED!`);
        console.log(`   📈 Type: ${activity.side}`);
        console.log(`   💰 Amount: $${activity.usdcSize?.toFixed(2)}`);
        console.log(`   📊 Price: ${activity.price}`);
        console.log(`   🎯 Market: ${activity.title}`);
        console.log(`   ⏰ Time: ${moment(activityTimestamp).format('YYYY-MM-DD HH:mm:ss')}`);
    }

    return newTradesCount;
};

/**
 * İşlemi veritabanına kaydet
 */
const saveActivityToDB = async (activity: UserActivityInterface, alreadyProcessed: boolean) => {
    try {
        const newActivity = new UserActivity({
            proxyWallet: activity.proxyWallet || USER_ADDRESS,
            timestamp: activity.timestamp,
            conditionId: activity.conditionId,
            type: activity.type,
            size: activity.size,
            usdcSize: activity.usdcSize,
            transactionHash: activity.transactionHash,
            price: activity.price,
            asset: activity.asset,
            side: activity.side,
            outcomeIndex: activity.outcomeIndex,
            title: activity.title,
            slug: activity.slug,
            icon: activity.icon,
            eventSlug: activity.eventSlug,
            outcome: activity.outcome,
            name: activity.name,
            pseudonym: activity.pseudonym,
            bio: activity.bio,
            profileImage: activity.profileImage,
            profileImageOptimized: activity.profileImageOptimized,
            bot: alreadyProcessed,
            botExcutedTime: 0,
        });

        await newActivity.save();
        
        // En son timestamp'i güncelle (milisaniye cinsinden sakla)
        const activityTimestampMs = (activity.timestamp || 0) * 1000;
        if (activityTimestampMs > lastFetchedTimestamp) {
            lastFetchedTimestamp = activityTimestampMs;
        }
    } catch (error: any) {
        // Duplicate key hatası olabilir, sessizce geç
        if (error.code !== 11000) {
            console.error('❌ Error saving activity:', error);
        }
    }
};

/**
 * Pozisyonları güncelle
 */
const updatePositions = async (positions: UserPositionInterface[]) => {
    try {
        for (const position of positions) {
            await UserPosition.findOneAndUpdate(
                { conditionId: position.conditionId },
                {
                    $set: {
                        proxyWallet: position.proxyWallet || USER_ADDRESS,
                        asset: position.asset,
                        conditionId: position.conditionId,
                        size: position.size,
                        avgPrice: position.avgPrice,
                        initialValue: position.initialValue,
                        currentValue: position.currentValue,
                        cashPnl: position.cashPnl,
                        percentPnl: position.percentPnl,
                        totalBought: position.totalBought,
                        realizedPnl: position.realizedPnl,
                        percentRealizedPnl: position.percentRealizedPnl,
                        curPrice: position.curPrice,
                        redeemable: position.redeemable,
                        mergeable: position.mergeable,
                        title: position.title,
                        slug: position.slug,
                        icon: position.icon,
                        eventSlug: position.eventSlug,
                        outcome: position.outcome,
                        outcomeIndex: position.outcomeIndex,
                        oppositeOutcome: position.oppositeOutcome,
                        oppositeAsset: position.oppositeAsset,
                        endDate: position.endDate,
                        negativeRisk: position.negativeRisk,
                    },
                },
                { upsert: true }
            );
        }
    } catch (error) {
        console.error('❌ Error updating positions:', error);
    }
};

/**
 * Kendi pozisyonlarımız için stop-loss/take-profit kontrolü
 */
const checkOwnPositionsForRisk = async () => {
    try {
        const myPositions: UserPositionInterface[] = await fetchData(
            `https://data-api.polymarket.com/positions?user=${PROXY_WALLET}`
        );

        for (const position of myPositions) {
            const shouldStopLoss = await riskManager.checkStopLoss(position);
            const shouldTakeProfit = await riskManager.checkTakeProfit(position);

            if (shouldStopLoss || shouldTakeProfit) {
                // Bu pozisyon için otomatik satış işlemi oluştur
                const action = shouldStopLoss ? 'STOP_LOSS' : 'TAKE_PROFIT';
                console.log(`\n⚠️ ${action} TRIGGERED!`);
                console.log(`   Market: ${position.title}`);
                console.log(`   PnL: ${position.percentPnl?.toFixed(2)}%`);
                console.log(`   Size: ${position.size}`);
                
                // Satış işlemi için yeni bir activity oluştur (bot tarafından)
                const sellActivity = new UserActivity({
                    proxyWallet: PROXY_WALLET,
                    timestamp: Date.now(),
                    conditionId: position.conditionId,
                    type: 'TRADE',
                    size: position.size,
                    usdcSize: position.currentValue,
                    transactionHash: `${action}_${Date.now()}`,
                    price: position.curPrice,
                    asset: position.asset,
                    side: 'SELL',
                    outcomeIndex: position.outcomeIndex,
                    title: position.title,
                    slug: position.slug,
                    icon: position.icon,
                    eventSlug: position.eventSlug,
                    outcome: position.outcome,
                    bot: false, // Henüz işlenmedi
                    botExcutedTime: 0,
                });

                await sellActivity.save();
            }
        }
    } catch (error) {
        console.error('❌ Error checking own positions:', error);
    }
};

/**
 * Ana veri çekme fonksiyonu
 */
const fetchTradeData = async () => {
    try {
        // 1. Kullanıcı aktivitelerini çek
        const activities = await fetchUserActivities();
        
        // 2. Yeni işlemleri işle
        const newTradesCount = await processNewTrades(activities);
        
        if (newTradesCount > 0) {
            console.log(`\n📊 Found ${newTradesCount} new trade(s) to copy`);
        }

        // 3. Kullanıcı pozisyonlarını güncelle
        const positions = await fetchUserPositions();
        await updatePositions(positions);

        // 4. Kendi pozisyonlarımız için risk kontrolü
        await checkOwnPositionsForRisk();

        // İlk çalışma tamamlandı
        if (isFirstRun) {
            isFirstRun = false;
            console.log('✅ Initial sync complete. Now monitoring for new trades...\n');
        }

    } catch (error) {
        console.error('❌ Error in fetchTradeData:', error);
    }
};

/**
 * Trade Monitor ana fonksiyonu
 */
const tradeMonitor = async () => {
    console.log('\n📡 Trade Monitor Starting...');
    console.log(`   👤 Target User: ${USER_ADDRESS}`);
    console.log(`   ⏱️  Fetch Interval: ${FETCH_INTERVAL} seconds`);
    console.log(`   📅 Too Old Threshold: ${TOO_OLD_TIMESTAMP} minutes\n`);

    await init();

    // Günlük sıfırlama için zamanlayıcı
    const scheduleNextDayReset = () => {
        const now = new Date();
        const tomorrow = new Date(now);
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(0, 0, 0, 0);
        const msUntilMidnight = tomorrow.getTime() - now.getTime();

        setTimeout(() => {
            riskManager.resetDailyStats();
            scheduleNextDayReset();
        }, msUntilMidnight);
    };
    scheduleNextDayReset();

    // Ana monitoring döngüsü
    while (true) {
        await fetchTradeData();
        await new Promise((resolve) => setTimeout(resolve, FETCH_INTERVAL * 1000));
    }
};

export default tradeMonitor;
export { fetchUserActivities, fetchUserPositions };
