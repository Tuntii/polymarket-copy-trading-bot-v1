import { ClobClient } from '@polymarket/clob-client';
import { UserActivityInterface, UserPositionInterface } from '../interfaces/User';
import { ENV } from '../config/env';
import { getUserActivityModel } from '../models/userHistory';
import fetchData from '../utils/fetchData';
import spinner from '../utils/spinner';
import getMyBalance from '../utils/getMyBalance';
import postOrder from '../utils/postOrder';
import riskManager from './riskManager';

const USER_ADDRESS = ENV.USER_ADDRESS;
const RETRY_LIMIT = ENV.RETRY_LIMIT;
const PROXY_WALLET = ENV.PROXY_WALLET;

let temp_trades: UserActivityInterface[] = [];

const UserActivity = getUserActivityModel(USER_ADDRESS);

const readTempTrade = async () => {
    temp_trades = (
        await UserActivity.find({
            $and: [{ type: 'TRADE' }, { bot: false }, { botExcutedTime: { $lt: RETRY_LIMIT } }],
        }).exec()
    ).map((trade) => trade as UserActivityInterface);
};

/**
 * Trade'in kopyalanabilir olup olmadığını kontrol et
 */
const canCopyTrade = async (
    trade: UserActivityInterface,
    currentPrice: number
): Promise<{ canCopy: boolean; adjustedAmount?: number; reason?: string }> => {
    const side = trade.side === 'BUY' ? 'BUY' : 'SELL';
    const originalPrice = trade.price || 0;
    const amount = trade.usdcSize || 0;

    // Risk kontrolü yap - title'ı da gönder (zaman kontrolü için)
    const riskCheck = await riskManager.performFullRiskCheck(
        side,
        amount,
        currentPrice,
        originalPrice,
        trade.conditionId || '',
        trade.title || '' // Market başlığı - zaman kontrolü için
    );

    if (!riskCheck.allowed) {
        return { canCopy: false, reason: riskCheck.reason };
    }

    return {
        canCopy: true,
        adjustedAmount: riskCheck.adjustedAmount || amount,
    };
};

/**
 * Trade durumunu belirle (buy, sell, merge)
 */
const determineTradeCondition = (
    trade: UserActivityInterface,
    my_position: UserPositionInterface | undefined,
    user_position: UserPositionInterface | undefined
): string => {
    // Merge durumu: Kullanıcı pozisyonunu tamamen kapattı
    if (trade.type === 'TRADE' && !user_position && my_position) {
        return 'merge';
    }

    // Normal buy/sell
    return trade.side === 'BUY' ? 'buy' : 'sell';
};

const doTrading = async (clobClient: ClobClient) => {
    for (const trade of temp_trades) {
        try {
            console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
            console.log('📋 Processing Trade:');
            console.log(`   Market: ${trade.title}`);
            console.log(`   Side: ${trade.side}`);
            console.log(`   Original Amount: $${trade.usdcSize?.toFixed(2)}`);
            console.log(`   Original Price: ${trade.price}`);
            console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

            // Mevcut pozisyonları al
            const my_positions: UserPositionInterface[] = await fetchData(
                `https://data-api.polymarket.com/positions?user=${PROXY_WALLET}`
            );
            const user_positions: UserPositionInterface[] = await fetchData(
                `https://data-api.polymarket.com/positions?user=${USER_ADDRESS}`
            );

            const my_position = my_positions.find(
                (position: UserPositionInterface) => position.conditionId === trade.conditionId
            );
            const user_position = user_positions.find(
                (position: UserPositionInterface) => position.conditionId === trade.conditionId
            );

            // Mevcut fiyatı al
            let currentPrice = trade.price || 0;
            try {
                const orderBook = await clobClient.getOrderBook(trade.asset || '');
                if (trade.side === 'BUY' && orderBook.asks && orderBook.asks.length > 0) {
                    currentPrice = parseFloat(orderBook.asks[0].price);
                } else if (trade.side === 'SELL' && orderBook.bids && orderBook.bids.length > 0) {
                    currentPrice = parseFloat(orderBook.bids[0].price);
                }
            } catch (error) {
                console.log('⚠️ Could not fetch current price, using original price');
            }

            console.log(`   Current Market Price: ${currentPrice}`);

            // Risk kontrolü
            const copyCheck = await canCopyTrade(trade, currentPrice);

            if (!copyCheck.canCopy) {
                console.log(`\n❌ Trade skipped: ${copyCheck.reason}`);
                await UserActivity.updateOne(
                    { _id: trade._id },
                    { bot: true, botExcutedTime: RETRY_LIMIT }
                );
                continue;
            }

            // Bakiye bilgisi
            const my_balance = await getMyBalance(PROXY_WALLET);
            const user_balance = await getMyBalance(USER_ADDRESS);

            console.log(`\n💰 Balance Info:`);
            console.log(`   My Balance: $${my_balance.toFixed(2)}`);
            console.log(`   Target User Balance: $${user_balance.toFixed(2)}`);
            console.log(`   Adjusted Trade Amount: $${copyCheck.adjustedAmount?.toFixed(2)}`);

            // Trade koşulunu belirle
            const condition = determineTradeCondition(trade, my_position, user_position);
            console.log(`\n🎯 Trade Condition: ${condition.toUpperCase()}`);

            // Trade'i gerçekleştir
            await postOrder(
                clobClient,
                condition,
                my_position,
                user_position,
                {
                    ...trade,
                    usdcSize: copyCheck.adjustedAmount ?? trade.usdcSize ?? 0, // Ayarlanmış miktar
                },
                my_balance,
                user_balance
            );

            // Trade'i kaydet
            riskManager.recordTrade();

            // Trade'i başarılı olarak işaretle (bir daha işlenmesin)
            await UserActivity.updateOne(
                { _id: trade._id },
                { bot: true, botExcutedTime: RETRY_LIMIT }
            );

            console.log('\n✅ Trade processed successfully\n');

        } catch (error) {
            console.error(`\n❌ Error processing trade:`, error);
            
            // Hata durumunda retry sayısını artır
            const currentRetry = (trade.botExcutedTime || 0) + 1;
            
            if (currentRetry >= RETRY_LIMIT) {
                // Retry limiti aşıldı, bir daha deneme
                await UserActivity.updateOne(
                    { _id: trade._id },
                    { bot: true, botExcutedTime: currentRetry }
                );
                console.log(`⚠️ Trade marked as processed after ${currentRetry} retries\n`);
            } else {
                // Retry sayısını artır
                await UserActivity.updateOne(
                    { _id: trade._id },
                    { botExcutedTime: currentRetry }
                );
                console.log(`🔄 Will retry (${currentRetry}/${RETRY_LIMIT})\n`);
            }
        }
    }
};

const tradeExecutor = async (clobClient: ClobClient) => {
    console.log('\n🚀 Trade Executor Starting...');
    console.log(`   💼 My Wallet: ${PROXY_WALLET}`);
    console.log(`   👤 Target User: ${USER_ADDRESS}`);
    console.log(`   🔄 Retry Limit: ${RETRY_LIMIT}\n`);

    // Risk durumunu göster
    try {
        const riskStatus = await riskManager.getRiskStatus();
        console.log('📊 Risk Configuration:');
        console.log(`   Max Position Size: $${riskStatus.config.maxPositionSizeUSDC}`);
        console.log(`   Max Daily Loss: $${riskStatus.config.maxDailyLossUSDC}`);
        console.log(`   Stop Loss: ${riskStatus.config.stopLossPercent}%`);
        console.log(`   Take Profit: ${riskStatus.config.takeProfitPercent}%`);
        console.log(`   Copy Ratio: ${riskStatus.config.copyRatioPercent}%`);
        console.log(`   Max Slippage: ${riskStatus.config.maxSlippagePercent}%\n`);
    } catch (error) {
        console.log('⚠️ Could not load risk status\n');
    }

    while (true) {
        await readTempTrade();
        
        if (temp_trades.length > 0) {
            console.log(`\n💥 Found ${temp_trades.length} trade(s) to process 💥`);
            spinner.stop();
            await doTrading(clobClient);
        } else {
            spinner.start('Waiting for new transactions');
        }

        // Kısa bir bekleme
        await new Promise((resolve) => setTimeout(resolve, 1000));
    }
};

export default tradeExecutor;
