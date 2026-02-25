import time
import random
import json
import asyncio
from typing import List, Dict, Any, Callable
from paper_trading import PaperTradingEngine, OrderSide, OrderType

class Backtester:
    def __init__(self, initial_capital: float = 100000.0):
        self.engine = PaperTradingEngine(initial_balance_usd=initial_capital)
        self.data: List[Dict] = [] # List of events (L2 snapshots, Trades)
        self.results: Dict = {}

    def load_mock_data(self, num_ticks=1000):
        """Generates synthetic random walk data for testing."""
        print(f"Generating {num_ticks} mock ticks...")
        price = 50000.0
        
        for i in range(num_ticks):
            # Random Walk
            change = (random.random() - 0.5) * 50
            price += change
            
            # Create a mock L2 snapshot
            snapshot = {
                "type": "depth",
                "timestamp": time.time() + i,
                "bids": [[price - j*5, 1.0] for j in range(5)],
                "asks": [[price + j*5, 1.0] for j in range(5)]
            }
            self.data.append(snapshot)
            
            # Create a mock Trade
            trade = {
                "type": "trade",
                "p": price,
                "q": 0.5,
                "m": random.choice([True, False]), # Maker/Taker
                "timestamp": time.time() + i
            }
            self.data.append(trade)

    async def run(self, strategy_callback: Callable):
        """
        Event Loop.
        strategy_callback(engine, event) is called on every tick.
        """
        print("Starting Backtest...")
        start_time = time.time()
        
        for event in self.data:
            # Update Engine State (simulated)
            if event["type"] == "trade":
                # Check if this trade fills any open limit orders
                # PaperTradingEngine expects a list of trades
                # We adapt the single trade to a list
                self.engine.process_limit_orders([event])
                
            # Invoke Strategy Logic
            await strategy_callback(self.engine, event)
            
        end_time = time.time()
        print(f"Backtest Complete. Duration: {end_time - start_time:.4f}s")
        self.engine._print_portfolio()

# Example Strategy for Backtesting
async def simple_strategy(engine: PaperTradingEngine, event: Dict):
    # Simple Logic: Buy if price drops below X (simulated by random check here)
    if event["type"] == "trade" and random.random() < 0.01:
        # Place a random order
        side = random.choice([OrderSide.BUY, OrderSide.SELL])
        price = float(event["p"])
        if side == OrderSide.BUY:
            price -= 50 # Buy Limit below market
        else:
            price += 50 # Sell Limit above market
            
        await engine.place_order("BTCUSDT", side, OrderType.LIMIT, 0.1, price)

if __name__ == "__main__":
    bt = Backtester()
    bt.load_mock_data(200)
    asyncio.run(bt.run(simple_strategy))
