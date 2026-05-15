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
- `main.py`: Main FastAPI entry point for the desktop dashboard.
- `phone.py`: Alternate FastAPI entry point for the phone-oriented UI.
- `backtester.py`: Historical-data backtester used by the `/api/backtest` endpoint.
- `download_data.py`: Downloads Binance data used for backtests.
- `paper_trading.py`: Paper execution and portfolio simulation engine.
- `orderbook/`: Core order book package.
  - `engine.py`: Order book state management.
  - `metrics.py`: Microstructure metric calculations.
  - `broadcaster.py`: WebSocket broadcast loop.
- `templates/`: HTML templates for the desktop and phone views.
- `static/`: Shared frontend JavaScript and CSS assets.

## Notes
- The legacy prototype backtester has been removed. The project now uses a single backtesting module: `backtester.py`.
- The backtest endpoint downloads temporary 1-second BTCUSDT data on demand and deletes the CSV after the run completes.

## Troubleshooting
- **Chart not loading?** The app attempts to load `Lightweight Charts` from `unpkg` and falls back to `cdnjs`. Ensure you have an internet connection.
- **Heatmap blank?** It requires a few seconds of data to populate.
