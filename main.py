import asyncio
import json
import websockets
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import Optional

from orderbook.engine import OrderBook
from orderbook.broadcaster import Broadcaster
from paper_trading import PaperTradingEngine, OrderSide, OrderType

from backtester_v2 import BacktesterV2
import os

# Configuration
BINANCE_WS = "wss://stream.binance.com:9443/stream?streams=btcusdt@depth@100ms/btcusdt@trade"
SYMBOL = "BTCUSDT"

# Global instances
order_book = OrderBook()
broadcaster = Broadcaster()
paper_engine = PaperTradingEngine()
backtest_running = False

async def binance_listener():
    """
    Connects to Binance WebSocket and updates the order book.
    Also feeds trades to the PaperTradingEngine.
    """
    while True:
        try:
            async with websockets.connect(BINANCE_WS) as ws:
                print("Connected to Binance WebSocket")
                
                # Fetch snapshot first to initialize book
                order_book.load_snapshot(symbol=SYMBOL)
                print(f"Snapshot loaded. Last Update ID: {order_book.last_update_id}")

                # Process stream
                async for msg in ws:
                    message = json.loads(msg)
                    stream_name = message.get("stream")
                    data = message.get("data")
                    
                    if not data:
                        continue
                        
                    if "depth" in stream_name:
                        try:
                            order_book.apply_diff(data, strict=False)
                        except Exception as e:
                            if str(e) == "ID GAP":
                                print("Order Book Gap detected, reloading...")
                                break
                            elif str(e) == "Bridging failed":
                                 pass
                            else:
                                print(f"Update error: {e}")
                                break
                                
                    elif "trade" in stream_name:
                        try:
                            order_book.process_trade(data)
                            # Feed trade to Paper Engine for Limit Order matching
                            # data is a single trade dict
                            paper_engine.process_limit_orders([data])
                        except Exception as e:
                            print(f"Trade processing error: {e}")

        except Exception as e:
            print(f"Binance listener error: {e}")
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting OrderBook Engine...")
    task_listener = asyncio.create_task(binance_listener())
    # Pass paper_engine to broadcaster so it can include portfolio data
    task_broadcaster = asyncio.create_task(broadcaster.start_broadcasting(order_book, paper_engine))
    yield
    # Shutdown
    task_listener.cancel()
    task_broadcaster.cancel()
    try:
        await task_listener
        await task_broadcaster
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        broadcaster.disconnect(websocket)

@app.get("/api/snapshot")
async def get_snapshot():
    """Returns the current ladder payload as JSON (Polling fallback)."""
    payload = order_book.ladder_payload(depth=13)
    current_price = payload.get("metrics", {}).get("mid", 0.0)
    payload["portfolio"] = paper_engine.get_portfolio_snapshot(current_price)
    return JSONResponse(payload)

@app.post("/api/order")
async def place_order(
    side: str = Body(...), 
    quantity: float = Body(...), 
    order_type: str = Body("MARKET"), 
    price: Optional[float] = Body(0.0)
):
    """
    Place a paper order.
    """
    # Convert string to Enum
    try:
        side_enum = OrderSide(side.upper())
        type_enum = OrderType(order_type.upper())
    except ValueError:
        return JSONResponse({"error": "Invalid side or type"}, status_code=400)

    # Place order
    order_id = await paper_engine.place_order(SYMBOL, side_enum, type_enum, quantity, price)
    
    # If Market Order, try to fill immediately against current book
    if type_enum == OrderType.MARKET:
        # We need a snapshot of the book. order_book is global.
        # Ideally we should lock, but for this simple engine it's okay.
        paper_engine.process_market_order(order_id, order_book)
        
    return JSONResponse({"order_id": order_id, "status": "accepted"})

@app.post("/api/cancel_all")
async def cancel_all():
    count = paper_engine.cancel_all_orders()
    return JSONResponse({"status": "cancelled", "count": count})

@app.post("/api/reset")
async def reset_account():
    # Use reset() method to preserve instance reference for broadcaster
    paper_engine.reset()
    return JSONResponse({"status": "reset"})

@app.post("/api/settings")
async def update_settings(
    fees_enabled: bool = Body(..., embed=True)
):
    paper_engine.set_fees(fees_enabled)
    return JSONResponse({"status": "updated", "fees_enabled": fees_enabled})

@app.post("/api/backtest")
async def run_backtest(fees: bool = True):
    """
    Triggers a backtest simulation on historical data.
    Runs in a separate thread to prevent blocking the event loop.
    """
    global backtest_running
    if backtest_running:
        return JSONResponse({"status": "running", "message": "Backtest already in progress"})
        
    def _run_backtest_task(fees_enabled):
        try:
            # Use 1s resolution for 24h as requested
            data_path = "backtest_data/BTCUSDT_1s_1d.csv"
            
            # Always download fresh or check existing
            if not os.path.exists(data_path):
                 import download_data
                 # Download 1 day of 1s klines
                 download_data.download_klines("BTCUSDT", "1s", days=1)
            
            bt = BacktesterV2(data_path)
            bt.load_data()
            
            # Run Fast Backtest
            results = bt.run_fast_backtest(include_fees=fees_enabled)
            
            # Cleanup data as requested
            if os.path.exists(data_path):
                os.remove(data_path)
                print(f"Deleted temporary backtest data: {data_path}")
                
            return results
        except Exception as e:
            print(f"Backtest error: {e}")
            raise e

    try:
        backtest_running = True
        # Run in thread pool
        results = await asyncio.to_thread(_run_backtest_task, fees)
        
        backtest_running = False
        return JSONResponse({"status": "completed", "results": results})
        
    except Exception as e:
        backtest_running = False
        print(f"Backtest error: {e}")
        return JSONResponse({"status": "error", "message": str(e)})

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)