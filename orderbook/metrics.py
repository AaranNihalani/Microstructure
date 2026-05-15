from typing import List, Tuple, Dict, Any, Optional

def calculate_imbalance(bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], depth: int = 10) -> float:
    """
    Calculate order book imbalance based on volume at top levels.
    Imbalance = (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
    Range: [-1, 1]
    Positive -> Buy pressure
    Negative -> Sell pressure
    """
    # Sum volume for top depth levels
    bid_vol = sum(q for _, q in bids[:depth])
    ask_vol = sum(q for _, q in asks[:depth])
    
    total_vol = bid_vol + ask_vol
    if total_vol == 0:
        return 0.0
        
    return (bid_vol - ask_vol) / total_vol

def calculate_spread(best_bid: float, best_ask: float) -> float:
    if best_bid is None or best_ask is None:
        return 0.0
    return best_ask - best_bid

def calculate_midprice(best_bid: float, best_ask: float) -> float:
    if best_bid is None or best_ask is None:
        return 0.0
    return (best_bid + best_ask) / 2.0

def calculate_microprice(best_bid: float, best_ask: float, best_bid_qty: float, best_ask_qty: float) -> float:
    """
    Microprice = (Bid Price * Ask Vol + Ask Price * Bid Vol) / (Bid Vol + Ask Vol)
    
    This price is weighted by the volume on the opposite side.
    If Bid Volume is huge, the price is pulled towards the Ask (upwards).
    The logic is that huge bid volume implies upward pressure.
    """
    if best_bid is None or best_ask is None:
        return 0.0
    
    total_qty = best_bid_qty + best_ask_qty
    if total_qty == 0:
        return (best_bid + best_ask) / 2.0
        
    return (best_bid * best_ask_qty + best_ask * best_bid_qty) / total_qty

def calculate_ofi_step(
    current_bid: float, current_bid_qty: float,
    prev_bid: float, prev_bid_qty: float,
    current_ask: float, current_ask_qty: float,
    prev_ask: float, prev_ask_qty: float
) -> float:
    """
    Calculate the OFI (Order Flow Imbalance) contribution for a single update step.
    Based on Cont et al. (2014).
    
    e_i = e_i(bid) - e_i(ask)
    
    Bid Contribution:
    - Price Increase: +Current Qty (All volume at new level is considered 'added' pressure)
    - Price Decrease: -Prev Qty (Support collapsed, pressure removed)
    - Price Constant: Change in Qty (Net added/removed limit orders)
    
    Ask Contribution (Subtracted from Total):
    - Price Decrease: +Current Qty (Resistance moved down, sell pressure added)
    - Price Increase: -Prev Qty (Resistance moved up, sell pressure removed)
    - Price Constant: Change in Qty
    """
    
    # Bid Contribution (Buy Pressure)
    if current_bid > prev_bid:
        e_bid = current_bid_qty
    elif current_bid < prev_bid:
        e_bid = -prev_bid_qty
    else: # current_bid == prev_bid
        e_bid = current_bid_qty - prev_bid_qty
        
    # Ask Contribution (Sell Pressure)
    # Note: We subtract this from the total OFI, so a positive e_ask means MORE sell pressure (lowering OFI)
    if current_ask < prev_ask:
        e_ask = current_ask_qty
    elif current_ask > prev_ask:
        e_ask = -prev_ask_qty
    else: # current_ask == prev_ask
        e_ask = current_ask_qty - prev_ask_qty
        
    return e_bid - e_ask

def calculate_vpin(volume_buckets: List[Tuple[float, float]]) -> float:
    """
    Calculate VPIN (Volume-Synchronized Probability of Informed Trading).
    VPIN = sum(|BuyVol - SellVol|) / sum(BuyVol + SellVol) over n buckets.
    
    Args:
        volume_buckets: List of (buy_vol, sell_vol) tuples.
    """
    numerator = sum(abs(buy - sell) for buy, sell in volume_buckets)
    denominator = sum(buy + sell for buy, sell in volume_buckets)
    
    if denominator == 0:
        return 0.0
        
    return numerator / denominator
