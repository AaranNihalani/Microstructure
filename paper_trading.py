import asyncio
import time
import uuid
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"  # Simulating latency
    OPEN = "OPEN"        # In the book
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float  # Limit price (None for Market)
    created_at: float
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: float = 0.0
    
    # For Limit Order Queue Simulation
    initial_queue_position: float = 0.0 # Volume ahead of us
    processed_volume: float = 0.0       # Volume traded at this price since placement

class PaperTradingEngine:
    def __init__(self, initial_balance_usd: float = 100000.0, maker_fee: float = 0.0002, taker_fee: float = 0.0004):
        # Account State
        self.balance_usd = initial_balance_usd
        self.balance_btc = 0.0
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Order Management
        self.orders: Dict[str, Order] = {}
        self.open_orders: List[str] = [] # IDs of OPEN orders
        
        # Latency Simulation (ms)
        self.min_latency = 50
        self.max_latency = 200
        
        # Metrics
        self.realized_pnl = 0.0
        self.total_volume_traded = 0.0
        
        # Settings
        self.fees_enabled = True

    def reset(self):
        """Resets the account state to initial values."""
        self.balance_usd = 100000.0
        self.balance_btc = 0.0
        self.orders.clear()
        self.open_orders.clear()
        self.realized_pnl = 0.0
        self.total_volume_traded = 0.0
        print("[PaperTrade] Account Reset")

    def set_fees(self, enabled: bool):
        self.fees_enabled = enabled
        print(f"[PaperTrade] Fees {'Enabled' if enabled else 'Disabled'}")

    def _get_latency_delay(self) -> float:
        return random.uniform(self.min_latency, self.max_latency) / 1000.0

    async def place_order(self, symbol: str, side: OrderSide, order_type: OrderType, quantity: float, price: float = 0.0) -> str:
        order_id = str(uuid.uuid4())
        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            created_at=time.time()
        )
        self.orders[order_id] = order
        
        # Simulate Network Latency before it hits the matching engine
        delay = self._get_latency_delay()
        await asyncio.sleep(delay)
        
        # Ack
        if order_type == OrderType.LIMIT:
            order.status = OrderStatus.OPEN
            self.open_orders.append(order_id)
            # In a real engine, we'd snapshot the current volume at this price level here
            # For this simplified version, we assume we are at the back of the queue
            # We'll need the current orderbook state to set initial_queue_position accurately
            # but we'll handle that in the on_tick / integration layer
            print(f"[PaperTrade] Limit Order OPEN: {side} {quantity} @ {price}")
            
        elif order_type == OrderType.MARKET:
            # Market orders are filled immediately (simulated in process_market_order)
            # We mark as PENDING until the engine processes it against the book
            # For simplicity in this async method, we'll mark it ready to be filled
            pass

        return order_id

    def process_market_order(self, order_id: str, order_book: Any):
        """
        Executes a market order immediately against the provided OrderBook snapshot.
        Walking the book logic.
        """
        order = self.orders.get(order_id)
        if not order or order.status == OrderStatus.FILLED:
            return

        remaining_qty = order.quantity
        total_cost = 0.0
        avg_price_accum = 0.0
        
        # Determine liquidity source
        ladder = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        # Sort: Asks ascending, Bids descending
        # Assuming order_book.asks/bids are list of [price, qty]
        # Bids in engine.py are SortedDict (Price -> Qty). 
        # We need to iterate correctly.
        
        liquidity = []
        if order.side == OrderSide.BUY:
            # Buying takes from Asks (lowest first)
            # Asks are sorted ascending (Low -> High)
            liquidity = list(order_book.asks.items())
        else:
            # Selling takes from Bids (highest first)
            # Bids are stored with negative keys (-Price).
            # SortedDict sorts -100 < -99, so (-100, qty) comes first.
            # This corresponds to Price 100 (Highest Bid).
            # So we do NOT need to reverse.
            liquidity = list(order_book.bids.items())

        for raw_price, vol in liquidity:
            if remaining_qty <= 0:
                break
            
            # If side is SELL, raw_price is negative (from Bids key)
            price = abs(raw_price)
                
            fill_qty = min(remaining_qty, vol)
            total_cost += fill_qty * price
            remaining_qty -= fill_qty
        
        if remaining_qty > 0:
            print(f"[PaperTrade] Warning: Partial fill for Market Order {order_id}. Not enough liquidity.")
            # In simulation, maybe we just wait or cancel remaining?
            # Let's fill what we can.
            
        filled_qty = order.quantity - remaining_qty
        avg_price = total_cost / filled_qty if filled_qty > 0 else 0.0
        
        self._finalize_fill(order, filled_qty, avg_price, is_maker=False)

    def process_limit_orders(self, trade_stream: List[Dict]):
        """
        Updates queue position of open limit orders based on Trade Stream.
        If a trade happens at our price or better, we advance in queue.
        """
        for trade in trade_stream:
            price = float(trade['p'])
            qty = float(trade['q'])
            is_buyer_maker = trade['m'] # True if buyer is maker (Sell trade)
            
            # If Sell Trade (Buyer Maker): Matches Bids
            # If Buy Trade (Seller Maker): Matches Asks
            
            for oid in list(self.open_orders):
                order = self.orders[oid]
                
                # Logic:
                # If I have a BUY Limit @ 50000.
                # Market Sells (Sell Trades) happen at 50000.
                # These trades consume the Bid Queue.
                
                if order.side == OrderSide.BUY:
                    if price < order.price:
                        # Price went below my limit -> I must have been filled
                        self._finalize_fill(order, order.quantity, order.price, is_maker=True)
                        self.open_orders.remove(oid)
                    elif price == order.price:
                        # Trade at my price. Did it eat my queue?
                        # Only Sell trades eat into Buy Limits
                        if is_buyer_maker: # Buyer is Maker = Sell Trade hitting Bid
                            order.processed_volume += qty
                            # Simplified: We assume we need to wait for X volume (random/heuristic)
                            # Ideally we captured the snapshot volume ahead of us.
                            # For now, let's say if we see volume > order.quantity * 5, we fill (conservative)
                            if order.processed_volume > order.quantity: 
                                self._finalize_fill(order, order.quantity, order.price, is_maker=True)
                                self.open_orders.remove(oid)

                elif order.side == OrderSide.SELL:
                    if price > order.price:
                        # Price went above my limit -> Filled
                        self._finalize_fill(order, order.quantity, order.price, is_maker=True)
                        self.open_orders.remove(oid)
                    elif price == order.price:
                        # Trade at my price.
                        # Only Buy trades eat into Sell Limits
                        if not is_buyer_maker: # Buyer is Taker = Buy Trade hitting Ask
                            order.processed_volume += qty
                            if order.processed_volume > order.quantity:
                                self._finalize_fill(order, order.quantity, order.price, is_maker=True)
                                if oid in self.open_orders: self.open_orders.remove(oid)

    def cancel_order(self, order_id: str):
        if order_id in self.open_orders:
            self.open_orders.remove(order_id)
            self.orders[order_id].status = OrderStatus.CANCELLED
            print(f"[PaperTrade] CANCELLED {order_id}")
            return True
        return False

    def cancel_all_orders(self):
        count = len(self.open_orders)
        for order_id in list(self.open_orders):
            self.orders[order_id].status = OrderStatus.CANCELLED
        self.open_orders.clear()
        print(f"[PaperTrade] CANCELLED {count} orders")
        return count

    def _finalize_fill(self, order: Order, qty: float, price: float, is_maker: bool):
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        cost = qty * price
        
        # Calculate fee
        fee = 0.0
        if self.fees_enabled:
            fee = cost * fee_rate
        
        if order.side == OrderSide.BUY:
            self.balance_usd -= cost
            self.balance_btc += qty
            # Fees usually deducted from received asset (BTC) or quote (USD)? 
            # Binance deducts from received. Buy -> Get BTC -> Pay BTC fee.
            # Simplified: Deduct USD equivalent from balance for easier PnL tracking
            self.balance_usd -= fee 
        else:
            self.balance_btc -= qty
            self.balance_usd += cost
            self.balance_usd -= fee

        order.filled_quantity = qty
        order.average_price = price
        order.status = OrderStatus.FILLED
        self.total_volume_traded += cost
        
        print(f"[PaperTrade] FILLED {order.side.value} {qty} @ {price:.2f} (Fee: {fee:.4f})")
        self._print_portfolio()

    def _print_portfolio(self):
        # Calculate approximate Net Worth using last fill price as mark
        print(f"--- PORTFOLIO ---")
        print(f"USD: {self.balance_usd:.2f}")
        print(f"BTC: {self.balance_btc:.4f}")
        print(f"Fees: {'On' if self.fees_enabled else 'Off'}")
        print(f"-----------------")

    def get_portfolio_snapshot(self, current_price: float = 0.0) -> Dict:
        equity = self.balance_usd
        if current_price > 0:
            equity += self.balance_btc * current_price
            
        return {
            "usd": self.balance_usd,
            "btc": self.balance_btc,
            "equity": equity,
            "fees_enabled": self.fees_enabled,
            "open_orders": len(self.open_orders)
        }