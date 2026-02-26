import pandas as pd
import numpy as np
from datetime import datetime
import json
import asyncio
from paper_trading import PaperTradingEngine, OrderSide, OrderType
from orderbook.engine import OrderBook

class BacktesterV2:
    def __init__(self, data_path, symbol="BTCUSDT"):
        self.data_path = data_path
        self.symbol = symbol
        self.paper_engine = PaperTradingEngine()
        self.paper_engine.set_fees(True) # Backtest with fees by default
        self.order_book = OrderBook()
        
        self.results = {}
        self.pnl_history = []
        
    def load_data(self):
        """Loads trade or kline data."""
        try:
            self.df = pd.read_csv(self.data_path)
            self.df.sort_values(by="timestamp", inplace=True)
            print(f"Loaded {len(self.df)} rows from {self.data_path}")
        except Exception as e:
            print(f"Error loading data: {e}")
            self.df = pd.DataFrame()

    def run_simulation(self):
        """
        Runs the strategy on historical data.
        Since we only have klines or trades, we simulate order book updates.
        """
        if self.df.empty:
            return {"error": "No data"}
            
        print("Starting Simulation...")
        
        # Initialize
        start_equity = self.paper_engine.equity
        self.pnl_history.append({"time": self.df.iloc[0]["timestamp"], "equity": start_equity})
        
        # Iterate through data
        # If we have trades, we can be more precise
        # If we have klines, we assume OHLC execution
        
        is_trade_data = 'price' in self.df.columns
        
        for index, row in self.df.iterrows():
            current_price = row['price'] if is_trade_data else row['close']
            timestamp = row['timestamp']
            
            # 1. Update Paper Engine Price
            # In a real backtest, we'd reconstruct the book.
            # Here, we update the "mid price" for valuation.
            
            # 2. Strategy Logic (Simplified HFT)
            # Calculate signals based on recent history
            # e.g., if price > moving_average -> Buy
            
            # 3. Check Orders
            # Simulate Limit Order fills
            # If we had a Limit Buy at X, and Low < X, fill it.
            
            # Let's simulate a simple strategy: Mean Reversion
            # If price drops 0.1% below 10-period MA, Buy.
            # If price rises 0.1% above 10-period MA, Sell.
            
            # We need a rolling window.
            # This is slow in Python loop, but okay for demo.
            
            pass # Placeholder for actual loop
            
        # Summary
        end_equity = self.paper_engine.get_portfolio_snapshot(current_price)['equity']
        pnl = end_equity - start_equity
        
        return {
            "start_equity": start_equity,
            "end_equity": end_equity,
            "pnl": pnl,
            "return_pct": (pnl / start_equity) * 100,
            "trades": len(self.paper_engine.orders),
            "data_points": len(self.df)
        }

    def run_fast_backtest(self):
        """
        Vectorized backtest for speed.
        """
        if self.df.empty: return {}
        
        # Calculate Indicators
        self.df['ma_50'] = self.df['close'].rolling(50).mean()
        self.df['std_50'] = self.df['close'].rolling(50).std()
        
        # Signal: Buy if Close < MA - 2*Std (Bollinger Lower)
        # Sell if Close > MA + 2*Std (Bollinger Upper)
        
        self.df['signal'] = 0
        self.df.loc[self.df['close'] < self.df['ma_50'] - 2*self.df['std_50'], 'signal'] = 1 # Buy
        self.df.loc[self.df['close'] > self.df['ma_50'] + 2*self.df['std_50'], 'signal'] = -1 # Sell
        
        # Calculate Returns
        self.df['pct_change'] = self.df['close'].pct_change()
        self.df['strategy_return'] = self.df['signal'].shift(1) * self.df['pct_change']
        
        # Transaction Costs (Fees)
        # Assuming Taker Fee of 0.04% (0.0004)
        taker_fee = 0.0004
        # Calculate turnover: change in position
        self.df['position_change'] = self.df['signal'].diff().abs()
        # Cost is turnover * fee
        self.df['costs'] = self.df['position_change'] * taker_fee
        
        # Net Return
        self.df['net_return'] = self.df['strategy_return'] - self.df['costs'].fillna(0)
        
        # Cumulative Return
        self.df['cum_return'] = (1 + self.df['net_return']).cumprod()
        
        total_return = self.df['cum_return'].iloc[-1] - 1 if not self.df.empty else 0
        
        # Max Drawdown
        rolling_max = self.df['cum_return'].cummax()
        drawdown = (self.df['cum_return'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100 # In percentage
        
        # Sharpe Ratio (Assuming 1m data, annualized)
        sharpe = 0
        if self.df['net_return'].std() > 0:
            sharpe = (self.df['net_return'].mean() / self.df['net_return'].std()) * np.sqrt(525600) # minutes in year
            
        return {
            "total_return_pct": total_return * 100,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "trades": int(self.df['position_change'].sum() / 2) # Divide by 2 for round trips approx
        }


if __name__ == "__main__":
    # Demo
    bt = BacktesterV2("backtest_data/BTCUSDT_1m_7d.csv")
    bt.load_data()
    print(bt.run_fast_backtest())