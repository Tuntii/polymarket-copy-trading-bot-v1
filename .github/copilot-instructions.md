# Polymarket Copy Trading Bot - AI Coding Instructions

You are working on a high-frequency copy trading bot for Polymarket, consisting of a Node.js/TypeScript backend and a React/Vite/Tailwind dashboard.

## 🏗 Project Architecture

### Components
- **Backend (`src/`)**: 
  - **Entry**: `src/index.ts` initializes the API server and `tradeExecutor`.
  - **Monitoring**: `src/services/realtimeMonitor.ts` connects to Polymarket Data API (polling/ws) to detect target trades and save them to MongoDB.
  - **Execution**: `src/services/tradeExecutor.ts` polls MongoDB for new *unprocessed* trades and executes them via `clob-client`.
  - **Risk**: `src/services/riskManager.ts` centralizes all trade validation logic (slippage, exposure, daily loss).
  - **API**: `src/api/server.ts` serves the Dashboard API and WebSocket for real-time logs/status.
- **Dashboard (`dashboard/`)**: 
  - React + Vite + Tailwind CSS application.
  - Communicates with backend via HTTP (`http://localhost:3001`) and WebSocket.

### Data Flow
1. **Detection**: `realtimeMonitor` sees a trade -> Saves to DB (`UserActivity` collection).
2. **Queue**: `tradeExecutor` loops, finding trades in DB where `bot: false` AND `timestamp >= START_TIME`.
3. **Validation**: `tradeExecutor` calls `RiskManager.performFullRiskCheck()`.
4. **Execution**: If valid, `postOrder()` submits to Polymarket CLOB.
5. **Feedback**: Status/Logs are sent to Dashboard via WebSocket (`addLog`, `addTrade`).

## 🛠 Development Workflow

### Startup Commands
- **Full Stack**: `npm run dev:all` (Recommended - runs bot & dashboard concurrently).
- **Backend Only**: `npm run dev`.
- **Dashboard Only**: `cd dashboard && npm run dev`.
- **Scripts**: Use `start.ps1` (Windows) or `start.sh` (Linux/Mac) for production-like startup.

### Environment
- **Strict Config**: All secrets/config must come from `.env`. 
- **Validation**: See `src/config/env.ts`. If adding a new var, update `ENV` object there.
- **Paper Trading**: Check `process.env.PAPER_TRADING === 'true'` before executing real orders.

## 📝 Coding Conventions

### Backend Patterns
- **Risk First**: Never bypass `RiskManager`. All trades must pass `performFullRiskCheck`.
- **Logging**: Use `addLog('INFO'|'SUCCESS'|'ERROR', msg)` from `src/api/server.ts` instead of `console.log` for user-facing events.
- **Dashboard Integration**: When adding a new feature, ensure it emits updates via WebSocket so the UI reflects state instantly.
- **Model Usage**: Use `UserActivityModel` for trade history.

### Frontend Patterns (Dashboard)
- **State**: Use `stats` state in `App.tsx` for real-time data data (pushed via WebSocket).
- **UI Components**: Use `src/components/ui` (Shadcn-like) for consistency.
- **API Hooks**: Use `useApi` hook for fetching initial state.

## ⚠️ Critical Implementation Details
- **Time Filtering**: The bot filters trades based on the *start time* of the process. See Logic in `tradeExecutor.ts` (`START_TIME`).
- **Order Books**: Polymarket CLOB may return 404 for orderbooks of closed markets. Handle this gracefully (see `tradeExecutor.ts`).
- **Latency**: `realtimeMonitor` creates the DB entry. `tradeExecutor` consumes it. Minimizing this gap is the performance bottleneck.

## 📂 Key Files
- `src/config/riskConfig.ts`: Default risk parameters.
- `src/utils/createClobClient.ts`: Ethers/CLOB authentication logic.
- `src/services/createClobClient.ts`: (Duplicate/Legacy) - Prefer `src/utils/`.
- `INTEGRATION_GUIDE.md`: Reference for API/Frontend contract.
