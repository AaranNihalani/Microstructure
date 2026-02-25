import asyncio
import json
import websockets
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from orderbook.engine import OrderBook
from orderbook.broadcaster import Broadcaster

# Configuration
BINANCE_WS = "wss://stream.binance.com:9443/stream?streams=btcusdt@depth@100ms/btcusdt@trade"
SYMBOL = "BTCUSDT"

# Global instances
order_book = OrderBook()
broadcaster = Broadcaster()

async def binance_listener():
    """
    Connects to Binance WebSocket and updates the order book.
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
    task_broadcaster = asyncio.create_task(broadcaster.start_broadcasting(order_book))
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
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception:
        broadcaster.disconnect(websocket)

@app.get("/api/snapshot")
async def get_snapshot():
    """Returns the current ladder payload as JSON (Polling fallback)."""
    return JSONResponse(order_book.ladder_payload(depth=10))

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
