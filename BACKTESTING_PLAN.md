# Backtesting Plan: Running Strategy on Last Week of Data

## Overview
This plan outlines the steps to implement a backtesting feature that allows running the Microstructure strategy (OFI, Microprice, Imbalance) on the last week of historical data.

## Challenges
1.  **Data Requirements**: The strategy relies on **Order Book Depth** (L2 Data) to calculate OFI and Microprice. Standard OHLCV (Candlestick) data is insufficient.
2.  **Data Volume**: 1 week of full depth updates (100ms) for BTCUSDT is extremely large (approx. 5-10GB of data).
3.  **Source**: Binance Public Data Collection offers monthly archives, but fetching "last week" requires downloading daily ZIP files of `depthUpdate` or `aggTrades`.

## Proposed Solution: "Replay Engine"

Instead of downloading 1 week of full depth data on the fly (which is slow and bandwidth-heavy), we will implement a **Trade Flow Replay** using `aggTrades` (Aggregated Trades). While less precise than full Depth OFI, we can approximate Order Flow Imbalance using Volume Order Imbalance (VOI) from trades.

### Step 1: Data Acquisition Script
Create a Python script `download_data.py` to fetch historical trade data.
- **Endpoint**: `GET /api/v3/aggTrades` (Binance REST API).
- **Parameters**: `startTime`, `endTime`.
- **Storage**: Save as CSV/Parquet chunks (e.g., `trades_2023-10-25.csv`).

### Step 2: Backtest Engine (`backtester_v2.py`)
Enhance the current `Backtester` to support "Event-Driven" replay.
- **Input**: Stream of historical trades.
- **State Reconstruction**: 
    - Maintain a local "Synthetic Orderbook" based on recent trade prices (approximated).
    - Or, switch strategy to use **Trade Imbalance** (Buyer vs Seller Maker volume) instead of Depth Imbalance.
- **Simulation**:
    - Feed trades into `PaperTradingEngine` as if they were live.
    - Match Limit Orders against historical trade prices.

### Step 3: Strategy Adaptation
Modify the strategy to work with Trade Data if Depth is unavailable:
- **OFI Proxy**: $OFI \approx V_{buy} - V_{sell}$ (Net Taker Volume).
- **Microprice Proxy**: VWAP (Volume Weighted Average Price) over short windows (1s).

## Implementation Roadmap

### Phase 1: Data Downloader (1 Day)
- [ ] Implement `fetch_historical_trades(symbol, days=7)`
- [ ] Save data to `data/` directory.

### Phase 2: Replay Simulation (2 Days)
- [ ] Create `ReplayLoop`:
  ```python
  for trade in historical_trades:
      strategy.on_trade(trade)
      if strategy.should_trade():
          engine.place_order(...)
      engine.process_fills(trade)
  ```

### Phase 3: Analysis & Visualization (1 Day)
- [ ] Generate PnL curve.
- [ ] Calculate Sharpe Ratio, Max Drawdown.
- [ ] Output HTML report.

## Alternative: Full Depth Backtest (High Effort)
If exact OFI replication is required:
1.  Use **Tardis.dev** or **Binance Vision** to download `depthUpdate` files.
2.  Replay `depthUpdate` messages to reconstruct the Order Book at every 100ms timestamp.
3.  Run the exact same logic as `main.py`.

*Recommendation*: Start with **Phase 1 & 2** (Trade Replay) to validate the execution logic before investing in Full Depth data infrastructure.
