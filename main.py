import asyncio
import json
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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

@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pro Microstructure Ladder</title>
    <style>
        body {
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'SF Mono', 'Roboto Mono', monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }
        .container {
            width: 480px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 15px;
        }
        
        /* Intro Section */
        .intro-box {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 15px;
            font-size: 12px;
            line-height: 1.4;
            color: #8b949e;
        }
        .intro-title {
            color: #f0f6fc;
            font-weight: bold;
            margin-bottom: 5px;
            display: block;
        }

        .header-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .metric-box {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 8px;
            text-align: center;
            position: relative;
        }
        .metric-label {
            font-size: 11px;
            color: #8b949e;
            margin-bottom: 4px;
            text-transform: uppercase;
            cursor: help;
            border-bottom: 1px dotted #8b949e;
            display: inline-block;
        }
        .metric-value {
            font-size: 14px;
            font-weight: bold;
            color: #f0f6fc;
        }
        
        /* Tooltip styling fixed */
        .metric-label:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #30363d;
            color: #f0f6fc;
            padding: 8px;
            border-radius: 4px;
            font-size: 11px;
            width: 200px;
            text-transform: none;
            z-index: 100;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            pointer-events: none;
            text-align: left;
            white-space: normal;
        }
        
        /* Special handling for left/right tooltips to avoid screen edge */
        .metric-box:first-child .metric-label:hover::after,
        .metric-box:nth-child(4) .metric-label:hover::after {
            left: 0;
            transform: translateX(0);
        }
        
        .metric-box:last-child .metric-label:hover::after,
        .metric-box:nth-child(3) .metric-label:hover::after {
            left: auto;
            right: 0;
            transform: translateX(0);
        }

        .imbalance-section {
            margin-bottom: 20px;
        }
        .imbalance-label {
            font-size: 11px;
            color: #8b949e;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
        }
        .imbalance-container {
            height: 8px;
            background: #30363d;
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }
        .imbalance-bar {
            height: 100%;
            width: 50%;
            transition: width 0.1s ease, background-color 0.2s ease;
        }
        
        .ladder {
            display: flex;
            flex-direction: column;
            gap: 1px;
            border-top: 1px solid #30363d;
            border-bottom: 1px solid #30363d;
            padding: 10px 0;
        }
        
        .ladder-header {
            display: grid;
            grid-template-columns: 80px 80px 1fr;
            padding-bottom: 5px;
            border-bottom: 1px solid #30363d;
            margin-bottom: 5px;
            font-size: 11px;
            color: #8b949e;
            font-weight: bold;
        }
        .header-cell {
            text-align: right;
        }
        .header-cell.price { padding-right: 15px; }
        .header-cell.size { padding-right: 10px; }
        .header-cell.total { padding-right: 5px; text-align: left; padding-left: 10px;}
        
        .row {
            display: grid;
            grid-template-columns: 80px 80px 1fr;
            height: 22px;
            align-items: center;
            position: relative;
            font-size: 13px;
        }
        .ask-row { color: #ff7b72; }
        .bid-row { color: #7ee787; }
        
        .price { text-align: right; padding-right: 15px; z-index: 2; font-weight: bold; }
        .size { text-align: right; padding-right: 10px; z-index: 2; color: #8b949e; }
        .total { text-align: right; padding-right: 5px; z-index: 2; font-size: 11px; color: #484f58; }
        
        .depth-bar {
            position: absolute;
            right: 0;
            top: 2px;
            bottom: 2px;
            opacity: 0.15;
            z-index: 1;
            border-radius: 2px;
        }
        .ask-bar { background-color: #ff7b72; }
        .bid-bar { background-color: #7ee787; }
        
        .spread-divider {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 24px;
            background: #161b22;
            color: #8b949e;
            font-size: 11px;
            border-top: 1px dashed #30363d;
            border-bottom: 1px dashed #30363d;
            margin: 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="intro-box">
            <span class="intro-title">Real-Time Microstructure Analysis</span>
            This tool visualizes the high-frequency BTC/USDT order book with advanced metrics. 
            It highlights hidden market pressure using Order Flow Imbalance (OFI), Microprice (Volume-Weighted Price), 
            and Cumulative Volume Delta (CVD) to help identify short-term price direction.
        </div>
    
        <div class="header-grid">
            <div class="metric-box">
                <div class="metric-label" data-tooltip="Best Ask - Best Bid. The cost of immediate execution.">Spread</div>
                <div id="spread" class="metric-value">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label" data-tooltip="(Bid + Ask) / 2. The simple middle price.">Mid Price</div>
                <div id="mid" class="metric-value">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label" data-tooltip="Volume-weighted Mid Price. Pulls towards the side with less liquidity (more likely to move there).">Microprice</div>
                <div id="micro" class="metric-value" style="color: #e3b341;">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label" data-tooltip="Order Book Imbalance [-1, 1]. Positive = Buy Pressure (More Bid Vol).">Imbalance</div>
                <div id="imb" class="metric-value">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label" data-tooltip="Order Flow Imbalance (Rolling). Net flow of limit orders adding pressure. >0 Buy, <0 Sell.">OFI (50)</div>
                <div id="ofi" class="metric-value">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label" data-tooltip="Cumulative Volume Delta. Net buying (taker) volume since start.">CVD</div>
                <div id="cvd" class="metric-value">--</div>
            </div>
        </div>

        <div class="imbalance-section">
            <div class="imbalance-label">
                <span>Sell Pressure</span>
                <span>Buy Pressure</span>
            </div>
            <div class="imbalance-container">
                <div id="imb-bar" class="imbalance-bar"></div>
            </div>
        </div>

        <div id="ladder" class="ladder">
            <div class="ladder-header">
                <div class="header-cell price">Price</div>
                <div class="header-cell size">Size</div>
                <div class="header-cell total">Visual Depth</div>
            </div>
            <div id="asks-container"></div>
            <div class="spread-divider" id="spread-info">--</div>
            <div id="bids-container"></div>
        </div>
    </div>

    <script>
        const DEPTH = 10;
        const wsUrl = "ws://" + location.host + "/ws";
        let ws;

        // Elements
        const els = {
            spread: document.getElementById('spread'),
            mid: document.getElementById('mid'),
            micro: document.getElementById('micro'),
            imb: document.getElementById('imb'),
            ofi: document.getElementById('ofi'),
            cvd: document.getElementById('cvd'),
            imbBar: document.getElementById('imb-bar'),
            asks: document.getElementById('asks-container'),
            bids: document.getElementById('bids-container'),
            spreadInfo: document.getElementById('spread-info')
        };

        const askRows = [];
        const bidRows = [];

        function createRow(type) {
            const row = document.createElement('div');
            row.className = `row ${type}-row`;
            
            const price = document.createElement('div');
            price.className = 'price';
            
            const size = document.createElement('div');
            size.className = 'size';
            
            const bar = document.createElement('div');
            bar.className = `depth-bar ${type}-bar`;
            
            row.appendChild(price);
            row.appendChild(size);
            row.appendChild(bar);
            
            return { el: row, price, size, bar };
        }

        function init() {
            // Asks: High -> Low (Visual top to bottom)
            for (let i = 0; i < DEPTH; i++) {
                const rowObj = createRow('ask');
                els.asks.appendChild(rowObj.el);
                askRows.push(rowObj);
            }

            // Bids: High -> Low
            for (let i = 0; i < DEPTH; i++) {
                const rowObj = createRow('bid');
                els.bids.appendChild(rowObj.el);
                bidRows.push(rowObj);
            }

            connect();
        }

        function connect() {
            ws = new WebSocket(wsUrl);
            ws.onmessage = onMessage;
            ws.onclose = () => setTimeout(connect, 1000);
            ws.onerror = () => ws.close();
        }

        function onMessage(event) {
            const data = JSON.parse(event.data);
            if (data.type !== 'ladder') return;

            const m = data.metrics;

            // Update Header Metrics
            els.spread.textContent = m.spread.toFixed(2);
            els.mid.textContent = m.mid.toFixed(2);
            els.micro.textContent = m.micro.toFixed(2);
            els.imb.textContent = m.imb.toFixed(3);
            els.ofi.textContent = m.ofi.toFixed(4);
            els.cvd.textContent = m.cvd.toFixed(4);
            
            // Colorize OFI/CVD/IMB
            els.ofi.style.color = m.ofi > 0 ? '#7ee787' : (m.ofi < 0 ? '#ff7b72' : '#f0f6fc');
            els.cvd.style.color = m.cvd > 0 ? '#7ee787' : (m.cvd < 0 ? '#ff7b72' : '#f0f6fc');
            els.imb.style.color = m.imb > 0 ? '#7ee787' : (m.imb < 0 ? '#ff7b72' : '#f0f6fc');

            // Imbalance Bar
            const bidShare = (m.imb + 1) / 2 * 100;
            els.imbBar.style.width = `${bidShare}%`;
            els.imbBar.style.backgroundColor = m.imb > 0 ? '#238636' : '#da3633';
            
            // Spread Divider Info
            els.spreadInfo.textContent = `Spread: ${m.spread.toFixed(2)} | Imb: ${(m.imb * 100).toFixed(1)}%`;

            // Max Volume for Bars
            let maxVol = 0;
            for (let i = 0; i < DEPTH; i++) {
                if (data.asks[i]) maxVol = Math.max(maxVol, data.asks[i][1]);
                if (data.bids[i]) maxVol = Math.max(maxVol, data.bids[i][1]);
            }
            if (maxVol === 0) maxVol = 1;

            // Update Asks (Render Reverse)
            for (let i = 0; i < DEPTH; i++) {
                const dataIndex = DEPTH - 1 - i;
                const item = data.asks[dataIndex];
                const row = askRows[i];

                if (item) {
                    row.price.textContent = item[0].toFixed(2);
                    row.size.textContent = item[1].toFixed(4);
                    const width = (item[1] / maxVol) * 100;
                    row.bar.style.width = `${width}%`;
                } else {
                    row.price.textContent = '';
                    row.size.textContent = '';
                    row.bar.style.width = '0%';
                }
            }

            // Update Bids (Render Normal)
            for (let i = 0; i < DEPTH; i++) {
                const item = data.bids[i];
                const row = bidRows[i];

                if (item) {
                    row.price.textContent = item[0].toFixed(2);
                    row.size.textContent = item[1].toFixed(4);
                    const width = (item[1] / maxVol) * 100;
                    row.bar.style.width = `${width}%`;
                } else {
                    row.price.textContent = '';
                    row.size.textContent = '';
                    row.bar.style.width = '0%';
                }
            }
        }

        init();
    </script>
</body>
</html>
    """)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
