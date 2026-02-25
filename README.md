# Pro Microstructure Ladder

A professional-grade real-time order book visualization tool for BTC/USDT, built with FastAPI and Vanilla JS.

## Features
- **Real-time Ladder**: 100ms updates via Binance WebSocket.
- **Advanced Metrics**:
  - **OFI (Order Flow Imbalance)**: Predicts short-term price pressure.
  - **Microprice**: Volume-weighted mid price.
  - **CVD (Cumulative Volume Delta)**: Net buyer/seller aggression.
  - **Imbalance**: Order book depth skew.
- **Visualizations**:
  - **Heatmap**: Historical depth evolution (Time x Price x Volume).
  - **Price Divergence**: Mid Price vs Microprice.
- **Resilience**:
  - Auto-reconnects WebSocket.
  - Falls back to HTTP polling if WebSocket fails (e.g., in serverless environments).

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Locally**:
   ```bash
   python main.py
   ```
   Open http://localhost:8000 in your browser.

## Project Structure
- `main.py`: Entry point, FastAPI app, and Frontend (HTML/JS).
- `orderbook/`: Core logic package.
  - `engine.py`: Order book state management (SortedDict).
  - `metrics.py`: Quant metric calculations.
  - `broadcaster.py`: WebSocket broadcasting logic.

## Troubleshooting
- **Chart not loading?** The app attempts to load `Lightweight Charts` from `unpkg` and falls back to `cdnjs`. Ensure you have an internet connection.
- **Heatmap blank?** It requires a few seconds of data to populate.
