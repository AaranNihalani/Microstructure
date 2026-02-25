import asyncio
import json
import requests
import websockets
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn

# ==============================
# Order Book Engine (Minimal)
# ==============================

class OrderBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}
        self.bid_prices = []
        self.ask_prices = []
        self.last_update_id = None

    def load_snapshot(self, symbol="BTCUSDT", limit=1000):
        url = "https://api.binance.com/api/v3/depth"
        params = {"symbol": symbol, "limit": limit}
        data = requests.get(url, params=params).json()

        self.last_update_id = data["lastUpdateId"]

        for price, qty in data["bids"]:
            self.bids[float(price)] = float(qty)

        for price, qty in data["asks"]:
            self.asks[float(price)] = float(qty)

    def apply_diff(self, event, strict=True):
        U = event["U"]
        u = event["u"]

        # Ignore outdated
        if u <= self.last_update_id:
            return

        if strict:
            # After startup: strict continuity
            if U != self.last_update_id + 1:
                raise Exception("ID GAP")
        else:
            # Startup bridging condition
            if not (U <= self.last_update_id + 1 <= u):
                raise Exception("Bridging failed")

        # Apply bids
        for price, qty in event["b"]:
            price = float(price)
            qty = float(qty)
            if qty == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = qty

        # Apply asks
        for price, qty in event["a"]:
            price = float(price)
            qty = float(qty)
            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty

        self.last_update_id = u

        print(order_book.midprice())
        # Integrity check
        if self.best_bid() and self.best_ask():
            if self.best_bid() >= self.best_ask():
                raise Exception("CROSSED BOOK")

    def best_bid(self):
        return max(self.bids.keys()) if self.bids else None

    def best_ask(self):
        return min(self.asks.keys()) if self.asks else None

    def spread(self):
        if self.best_bid() and self.best_ask():
            return self.best_ask() - self.best_bid()
        return None

    def midprice(self):
        if self.best_bid() and self.best_ask():
            return (self.best_bid() + self.best_ask()) / 2
        return None


# ==============================
# FastAPI App
# ==============================

app = FastAPI()
order_book = OrderBook()

BINANCE_WS = "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"


@app.on_event("startup")
async def startup_event():
    print("Loading snapshot...")
    order_book.load_snapshot()
    print("Starting Binance listener...")
    asyncio.create_task(binance_listener())


async def binance_listener():
    while True:
        try:
            async with websockets.connect(BINANCE_WS) as ws:

                buffer = []

                # Step 1: Start buffering
                snapshot = None

                # Fetch snapshot immediately
                snapshot = requests.get(
                    "https://api.binance.com/api/v3/depth",
                    params={"symbol": "BTCUSDT", "limit": 1000}
                ).json()

                S = snapshot["lastUpdateId"]

                # Load snapshot into book
                order_book.bids.clear()
                order_book.asks.clear()

                for price, qty in snapshot["bids"]:
                    order_book.bids[float(price)] = float(qty)

                for price, qty in snapshot["asks"]:
                    order_book.asks[float(price)] = float(qty)

                order_book.last_update_id = S

                # Step 2: Process stream
                async for msg in ws:
                    data = json.loads(msg)

                    U = data["U"]
                    u = data["u"]

                    # Ignore old updates
                    if u <= order_book.last_update_id:
                        continue

                    # First valid event
                    if order_book.last_update_id + 1 >= U and order_book.last_update_id + 1 <= u:
                        order_book.apply_diff(data, strict=False)
                        break

                # Step 3: Strict mode after alignment
                async for msg in ws:
                    data = json.loads(msg)
                    order_book.apply_diff(data, strict=True)

        except Exception as e:
            print("WebSocket error, restarting cleanly:", e)
            await asyncio.sleep(1)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    try:
        while True:
            await asyncio.sleep(0.1)

            state = {
                "best_bid": order_book.best_bid(),
                "best_ask": order_book.best_ask(),
                "spread": order_book.spread(),
                "mid": order_book.midprice(),
            }

            await websocket.send_json(state)

    except Exception:
        print("Client disconnected")


@app.get("/")
async def root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live BTC Order Book</title>
    </head>
    <body>
        <h2>BTCUSDT Live Book</h2>
        <div id="data">Connecting...</div>

        <script>
            const ws = new WebSocket("ws://" + location.host + "/ws");

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById("data").innerHTML =
                    "Best Bid: " + data.best_bid + "<br>" +
                    "Best Ask: " + data.best_ask + "<br>" +
                    "Spread: " + data.spread + "<br>" +
                    "Mid: " + data.mid;
            };
        </script>
    </body>
    </html>
    """)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)