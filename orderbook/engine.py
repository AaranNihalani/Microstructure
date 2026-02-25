from sortedcontainers import SortedDict
from typing import List, Dict, Any, Optional
from collections import deque
import requests
from .metrics import (
    calculate_imbalance, calculate_spread, calculate_midprice,
    calculate_microprice, calculate_ofi_step
)

class OrderBook:
    def __init__(self):
        # Bids: Key = -price (to keep sorted descending), Value = quantity
        self.bids = SortedDict()
        # Asks: Key = price (sorted ascending), Value = quantity
        self.asks = SortedDict()
        self.last_update_id = None
        
        # State for OFI calculation
        self.prev_best_bid: Optional[float] = None
        self.prev_best_bid_qty: Optional[float] = None
        self.prev_best_ask: Optional[float] = None
        self.prev_best_ask_qty: Optional[float] = None
        
        # Metrics History
        self.ofi_window = deque(maxlen=50) # Rolling window for OFI sum
        self.cvd = 0.0 # Cumulative Volume Delta

    def load_snapshot(self, symbol="BTCUSDT", limit=1000):
        try:
            url = "https://api.binance.com/api/v3/depth"
            params = {"symbol": symbol, "limit": limit}
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            self.last_update_id = data["lastUpdateId"]
            
            self.bids.clear()
            self.asks.clear()

            for price, qty in data["bids"]:
                self.bids[-float(price)] = float(qty)

            for price, qty in data["asks"]:
                self.asks[float(price)] = float(qty)
            
            # Initialize OFI state
            self._update_ofi_state()
                
        except Exception as e:
            # Silent fail or minimal log if needed, but keeping hot path clean
            pass

    def apply_diff(self, event: Dict[str, Any], strict: bool = True):
        U = event["U"]
        u = event["u"]

        if u <= self.last_update_id:
            return

        # Gap detection logic
        if strict:
            if U != self.last_update_id + 1:
                # Re-sync needed, raise exception to trigger restart
                raise Exception("ID GAP")
        else:
            if not (U <= self.last_update_id + 1 <= u):
                raise Exception("Bridging failed")

        # Update Bids
        for price_str, qty_str in event["b"]:
            price = float(price_str)
            qty = float(qty_str)
            key = -price
            
            if qty == 0:
                if key in self.bids:
                    del self.bids[key]
            else:
                self.bids[key] = qty

        # Update Asks
        for price_str, qty_str in event["a"]:
            price = float(price_str)
            qty = float(qty_str)
            
            if qty == 0:
                if price in self.asks:
                    del self.asks[price]
            else:
                self.asks[price] = qty

        self.last_update_id = u
        
        # Calculate and update OFI after applying updates
        self._calculate_and_store_ofi()

    def process_trade(self, trade: Dict[str, Any]):
        """
        Process a trade event for CVD calculation.
        Binance Trade Event:
        "m": true -> Buyer is Maker -> Sell Trade
        "m": false -> Buyer is Taker -> Buy Trade
        """
        qty = float(trade['q'])
        is_buyer_maker = trade['m']
        
        # Accumulate volume buckets for VPIN (simplified: just tracking total vol for now)
        # In a real implementation, we would bucket this by volume bars
        
        if is_buyer_maker:
            # Seller is Taker -> Sell Trade
            self.cvd -= qty
        else:
            # Buyer is Taker -> Buy Trade
            self.cvd += qty

    def _update_ofi_state(self):
        """Update the previous state variables for next OFI calculation"""
        best_bid_item = self.bids.peekitem(0) if self.bids else None
        best_ask_item = self.asks.peekitem(0) if self.asks else None
        
        if best_bid_item:
            self.prev_best_bid = -best_bid_item[0]
            self.prev_best_bid_qty = best_bid_item[1]
        else:
            self.prev_best_bid = None
            self.prev_best_bid_qty = 0.0
            
        if best_ask_item:
            self.prev_best_ask = best_ask_item[0]
            self.prev_best_ask_qty = best_ask_item[1]
        else:
            self.prev_best_ask = None
            self.prev_best_ask_qty = 0.0

    def _calculate_and_store_ofi(self):
        """Calculate OFI step and update rolling window"""
        # Get current bests
        best_bid_item = self.bids.peekitem(0) if self.bids else None
        best_ask_item = self.asks.peekitem(0) if self.asks else None
        
        curr_bid = -best_bid_item[0] if best_bid_item else 0.0
        curr_bid_qty = best_bid_item[1] if best_bid_item else 0.0
        
        curr_ask = best_ask_item[0] if best_ask_item else 0.0
        curr_ask_qty = best_ask_item[1] if best_ask_item else 0.0
        
        # If we have history, calculate step
        if (self.prev_best_bid is not None and self.prev_best_ask is not None and
            curr_bid > 0 and curr_ask > 0): # Ensure valid prices
            
            ofi_step = calculate_ofi_step(
                curr_bid, curr_bid_qty,
                self.prev_best_bid, self.prev_best_bid_qty,
                curr_ask, curr_ask_qty,
                self.prev_best_ask, self.prev_best_ask_qty
            )
            self.ofi_window.append(ofi_step)
            
        # Update state for next time
        self.prev_best_bid = curr_bid
        self.prev_best_bid_qty = curr_bid_qty
        self.prev_best_ask = curr_ask
        self.prev_best_ask_qty = curr_ask_qty

    def top_levels(self, side: str, depth: int = 10) -> List[List[float]]:
        """
        Returns list of [price, qty]
        """
        if side == 'bids':
            return [[-k, v] for k, v in self.bids.items()[:depth]]
        
        elif side == 'asks':
            return [[k, v] for k, v in self.asks.items()[:depth]]
        
        return []

    def get_best_bid(self) -> Optional[float]:
        if not self.bids:
            return None
        return -self.bids.peekitem(0)[0]

    def get_best_ask(self) -> Optional[float]:
        if not self.asks:
            return None
        return self.asks.peekitem(0)[0]

    def ladder_payload(self, depth: int = 10) -> Dict[str, Any]:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        # Get volumes for microprice
        best_bid_qty = self.bids.peekitem(0)[1] if self.bids else 0.0
        best_ask_qty = self.asks.peekitem(0)[1] if self.asks else 0.0
        
        bids_data = self.top_levels('bids', depth)
        asks_data = self.top_levels('asks', depth)
        
        imb = calculate_imbalance(bids_data, asks_data, depth)
        spread = calculate_spread(best_bid, best_ask)
        mid = calculate_midprice(best_bid, best_ask)
        micro = calculate_microprice(best_bid, best_ask, best_bid_qty, best_ask_qty)
        
        # Sum OFI window
        ofi_val = sum(self.ofi_window) if self.ofi_window else 0.0
        
        return {
            "type": "ladder",
            "bids": bids_data,
            "asks": asks_data,
            "metrics": {
                "imb": imb,
                "spread": spread,
                "mid": mid,
                "micro": micro,
                "ofi": ofi_val,
                "cvd": self.cvd
            }
        }
