import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from paper_trading import PaperTradingEngine, OrderSide, OrderType

class ExecutionAlgorithm(ABC):
    def __init__(self, engine: PaperTradingEngine, symbol: str, quantity: float, side: OrderSide):
        self.engine = engine
        self.symbol = symbol
        self.total_quantity = quantity
        self.side = side
        self.filled_quantity = 0.0
        self.is_active = True

    @abstractmethod
    async def on_tick(self, market_data: Dict[str, Any]):
        pass

class TWAP(ExecutionAlgorithm):
    """
    Time-Weighted Average Price.
    Slices the total order into N parts and executes them at regular intervals.
    """
    def __init__(self, engine: PaperTradingEngine, symbol: str, quantity: float, side: OrderSide, duration_seconds: int, num_slices: int):
        super().__init__(engine, symbol, quantity, side)
        self.duration = duration_seconds
        self.num_slices = num_slices
        self.slice_size = quantity / num_slices
        self.interval = duration_seconds / num_slices
        self.start_time = time.time()
        self.slices_executed = 0
        self.next_execution_time = self.start_time

    async def on_tick(self, market_data: Dict[str, Any]):
        if not self.is_active:
            return

        now = time.time()
        if now >= self.next_execution_time and self.slices_executed < self.num_slices:
            # Execute Slice
            print(f"[TWAP] Executing Slice {self.slices_executed + 1}/{self.num_slices}: {self.slice_size} {self.symbol}")
            
            # Simple Market Order for TWAP (or Aggressive Limit)
            await self.engine.place_order(
                self.symbol, 
                self.side, 
                OrderType.MARKET, 
                self.slice_size
            )
            
            self.slices_executed += 1
            self.filled_quantity += self.slice_size
            self.next_execution_time = now + self.interval
            
            if self.slices_executed >= self.num_slices:
                print("[TWAP] Execution Complete")
                self.is_active = False

class VWAP(ExecutionAlgorithm):
    """
    Volume-Weighted Average Price.
    Participates as a percentage of market volume.
    """
    def __init__(self, engine: PaperTradingEngine, symbol: str, quantity: float, side: OrderSide, participation_rate: float = 0.1):
        super().__init__(engine, symbol, quantity, side)
        self.participation_rate = participation_rate # Target 10% of volume
        self.accumulated_market_volume = 0.0
        self.last_check_volume = 0.0

    async def on_tick(self, market_data: Dict[str, Any]):
        if not self.is_active:
            return
            
        # Assuming market_data contains 'volume' or we track trades
        # For this simplified version, let's assume market_data is a Trade
        if market_data.get("type") == "trade":
            trade_qty = float(market_data['q'])
            self.accumulated_market_volume += trade_qty
            
            # Check if we need to catch up
            target_fill = self.accumulated_market_volume * self.participation_rate
            needed = target_fill - self.filled_quantity
            
            if needed > 0.001: # Minimum threshold
                # Execute catch-up slice
                print(f"[VWAP] Catching up: {needed:.4f} (Target: {target_fill:.4f})")
                await self.engine.place_order(
                    self.symbol,
                    self.side,
                    OrderType.MARKET,
                    needed
                )
                self.filled_quantity += needed
                
        if self.filled_quantity >= self.total_quantity:
            print("[VWAP] Execution Complete")
            self.is_active = False
