import connectDB from './config/db';
import { ENV } from './config/env';
import createClobClient from './utils/createClobClient';
import tradeExecutor from './services/tradeExecutor';
import { startRealtimeMonitoring } from './services/realtimeMonitor';

const USER_ADDRESS = ENV.USER_ADDRESS;
const PROXY_WALLET = ENV.PROXY_WALLET;

export const main = async () => {
    await connectDB();
    console.log(`Target User Wallet addresss is: ${USER_ADDRESS}`);
    console.log(`My Wallet addresss is: ${PROXY_WALLET}`);
    const clobClient = await createClobClient();
    
    console.log('\n🚀 INSTANT COPY MODE ACTIVATED');
    console.log('   ⚡ Real-time monitoring: 200ms polling');
    console.log('   🎯 Copy strategy: Mirror target user');
    console.log('   ⏱️  Expected latency: <1 second\n');
    
    // Start real-time monitoring - NO POLLING DELAY
    startRealtimeMonitoring((trade) => {
        console.log('⚡ Trade callback triggered - ready to copy!');
    });
    
    // Trade executor will handle the copying
    tradeExecutor(clobClient);
};

main();
