import requests
import pandas as pd
import time
import os
from datetime import datetime, timedelta
import zipfile
import io

# Constants
SYMBOL = "BTCUSDT"
INTERVAL = "1m" # Use 1m klines for approximation, or trades for precision
DATA_DIR = "backtest_data"

def download_klines(symbol, interval, days=7):
    """
    Downloads klines from Binance API for the last N days.
    """
    print(f"Downloading {days} days of {interval} data for {symbol}...")
    base_url = "https://api.binance.com/api/v3/klines"
    end_time = int(time.time() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    all_data = []
    current_start = start_time
    
    while current_start < end_time:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "limit": 1000
        }
        try:
            response = requests.get(base_url, params=params)
            data = response.json()
            if not data:
                break
            
            all_data.extend(data)
            current_start = data[-1][0] + 1
            # Rate limit respect
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error downloading: {e}")
            break
            
    # Convert to DataFrame
    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    
    # Clean types
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    df["timestamp"] = pd.to_datetime(df["open_time"], unit='ms')
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    filename = f"{DATA_DIR}/{symbol}_{interval}_{days}d.csv"
    df.to_csv(filename, index=False)
    print(f"Data saved to {filename}")
    return filename

def download_trades_snapshot(symbol, limit=10000):
    """
    Downloads recent trades for high-res simulation.
    """
    print(f"Downloading recent trades for {symbol}...")
    base_url = "https://api.binance.com/api/v3/aggTrades" # or trades
    
    # Get recent trades
    params = {"symbol": symbol, "limit": 1000} # Max limit per req
    
    all_trades = []
    
    # We want more than 1000, so we need to loop back
    # First request to get latest
    try:
        resp = requests.get(base_url, params=params)
        trades = resp.json()
        all_trades.extend(trades)
        
        # Loop back
        for _ in range(int(limit/1000) - 1):
            from_id = trades[0]['a'] - 1000
            params['fromId'] = from_id
            resp = requests.get(base_url, params=params)
            trades = resp.json()
            if not trades: break
            all_trades.extend(trades)
            trades.sort(key=lambda x: x['T']) # Ensure sort
            
    except Exception as e:
        print(f"Error fetching trades: {e}")
        
    df = pd.DataFrame(all_trades)
    if not df.empty:
        df['price'] = pd.to_numeric(df['p'])
        df['close'] = df['price'] # Alias for Backtester compatibility
        df['qty'] = pd.to_numeric(df['q'])
        df['timestamp'] = pd.to_datetime(df['T'], unit='ms')
        df['is_buyer_maker'] = df['m']
        
        filename = f"{DATA_DIR}/{symbol}_trades_snapshot.csv"
        df.to_csv(filename, index=False)
        print(f"Trades saved to {filename}")
        return filename
    return None

if __name__ == "__main__":
    download_klines(SYMBOL, INTERVAL)
    download_trades_snapshot(SYMBOL)