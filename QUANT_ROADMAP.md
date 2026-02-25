# Future Directions: Quant-Focused Roadmap

This roadmap outlines the next steps to transform this tool into a research-grade quantitative analysis platform.

## Phase 4: Order Flow Toxicity & Alpha Generation

### 1. VPIN (Volume-Synchronized Probability of Informed Trading)
*   **Concept**: Detects toxic order flow by measuring volume imbalance in volume buckets rather than time buckets.
*   **Implementation**:
    *   Aggregate trades into "volume buckets" (e.g., every 50 BTC traded).
    *   Compute buy/sell volume imbalance for each bucket.
    *   High VPIN -> High probability of informed trading (toxic flow).

### 2. Backtesting Engine
*   **Concept**: Evaluate microstructure strategies on historical data.
*   **Implementation**:
    *   **Data Recorder**: Persist full L2 updates and trades to Parquet/HDF5.
    *   **Simulator**: Build an event-driven backtester that simulates latency and queue position.
    *   **Strategy**: Test "Market Making" or "Scalping" strategies using the computed signals (OFI, Microprice).

### 3. Short-Term Price Prediction (Alpha)
*   **Concept**: Predict price moves over the next 1-10 seconds.
*   **Model**:
    *   **Features**: OFI (Order Flow Imbalance), Order Book Slope, Spread, Volume.
    *   **Algorithm**: Linear Regression (Online Learning) or LightGBM.
    *   **Output**: Probability of up/down tick.

## Phase 5: Execution Algorithms

### 1. TWAP / VWAP Execution
*   **Concept**: Execute large orders without impacting the market.
*   **Implementation**:
    *   Slice orders into child orders.
    *   Use **Microprice** to time the entries (passive placement when Microprice favors you).

### 2. Smart Order Router (SOR)
*   **Concept**: If connected to multiple exchanges.
*   **Implementation**: Route orders to the venue with the best price + lowest probability of adverse selection.

## Phase 6: Institutional Features

### 1. Latency Monitoring
*   **Concept**: Measure the time delta between "Exchange Timestamp" and "Local Receipt Timestamp".
*   **Goal**: Monitor network jitter and processing lag.

### 2. Queue Position Estimation
*   **Concept**: Estimate where your limit order sits in the queue.
*   **Implementation**: Track volume traded at your price level since you placed the order.
