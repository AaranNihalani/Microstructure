# Intelligent Paper Trading Engine Plan

This document outlines the architecture for a realistic Paper Trading Engine to simulate trading with $100,000 capital, accounting for latency, fees, and market impact.

## 1. Core Components

### A. Account State
*   **Balance**: Tracks USD and BTC holdings.
*   **PnL**: Realized and Unrealized Profit/Loss.
*   **Leverage**: Support for margin simulation (e.g., 1x, 5x).
*   **Fees**: Maker (0.02%) vs Taker (0.04%) fee simulation.

### B. Order Management System (OMS)
*   **Order Types**: Limit, Market, Stop-Loss.
*   **Order Book**: Internal "shadow" order book to track open orders.
*   **Matching Engine**:
    *   **Market Orders**: Execute immediately against the best available price in the live L2 stream, accounting for slippage (walking the book).
    *   **Limit Orders**: Placed in a virtual queue.
        *   **Queue Position**: When a limit order is placed, record the `cumulative_volume` at that price level.
        *   **Fill Logic**: The order fills only when `traded_volume` at that price level > `queue_position`.

### C. Latency Simulation
*   **Network Delay**: Add a randomized delay (e.g., 50-200ms) between "Order Sent" and "Order Ack/Fill".
*   **Processing Time**: Simulate exchange matching engine latency.

## 2. State Machine

1.  **Idle**: Waiting for strategy signal.
2.  **Order Sent**: Signal received -> Latency Delay -> Order reaches "Exchange".
3.  **Open**: Limit order sits in the book.
4.  **Filled**: Trade occurs -> Update Balance & PnL -> Deduct Fees.
5.  **Cancelled**: Order removed.

## 3. Implementation Steps

1.  Create `PaperExchange` class in Python.
2.  Subscribe to the `OrderBook` L2 updates and Trade stream.
3.  Implement `place_order(side, qty, price, type)` method.
4.  Implement `on_market_data(book_snapshot, trades)` loop to check for fills.
5.  Expose an API/UI to view "Paper Portfolio" performance.
