const DEPTH = 13;
const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + "/ws";
let ws;
let pollingInterval;
let isPolling = false;

// Auto-Trading State
let autoTradeEnabled = false;
let lastTradeTime = 0;
const TRADE_COOLDOWN = 500; // 500ms cooldown for HFT
const MAX_POSITION = 0.5;   // Increased Max inventory constraint
let tradeMarkers = []; // Store chart markers for trades
let latestData = null; // Store latest market data for order pricing

// Elements
const els = {
    spread: document.getElementById('spread'),
    mid: document.getElementById('mid'),
    micro: document.getElementById('micro'),
    imb: document.getElementById('imb'),
    ofi: document.getElementById('ofi'),
    cvd: document.getElementById('cvd'),
    intensity: document.getElementById('intensity'),
    volatility: document.getElementById('volatility'),
    imbBar: document.getElementById('imb-bar'),
    asks: document.getElementById('asks-container'),
    bids: document.getElementById('bids-container'),
    spreadInfo: document.getElementById('spread-info'),
    status: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text'),
    heatmapCanvas: document.getElementById('heatmap-canvas'),
    // ... other elements ...
    insightsText: document.getElementById('insights-text'),
    // Paper Trading Elements
    ptUsd: document.getElementById('pt-usd'),
    ptBtc: document.getElementById('pt-btc'),
    ptEquity: document.getElementById('pt-equity'),
    // Buttons
    autoTradeBtn: document.getElementById('auto-trade-btn'),
    backtestBtn: document.getElementById('run-backtest-btn'),
    backtestResults: document.getElementById('backtest-results')
};

// --- Backtesting Logic ---
if (els.backtestBtn) {
    els.backtestBtn.addEventListener('click', async () => {
        els.backtestResults.style.display = 'block';
        els.backtestResults.innerHTML = '<span style="color:#e3b341">Running simulation... this may take a moment.</span>';
        
        try {
            const res = await fetch('/api/backtest', {method: 'POST'});
            const data = await res.json();
            
            if (data.status === 'completed') {
                const r = data.results;
                els.backtestResults.innerHTML = `
                    <div style="color:#7ee787; font-weight:bold; margin-bottom:5px;">Simulation Complete</div>
                    <div>Return: <span style="color:${r.total_return_pct >= 0 ? '#7ee787' : '#da3633'}">${r.total_return_pct.toFixed(2)}%</span></div>
                    <div>Sharpe: ${r.sharpe_ratio.toFixed(2)}</div>
                    <div>Max DD: ${r.max_drawdown.toFixed(2)}%</div>
                `;
            } else if (data.status === 'running') {
                els.backtestResults.innerHTML = '<span style="color:#e3b341">Backtest already running...</span>';
            } else {
                els.backtestResults.innerHTML = `<span style="color:#da3633">Error: ${data.message}</span>`;
            }
        } catch (e) {
             els.backtestResults.innerHTML = `<span style="color:#da3633">Network Error: ${e.message}</span>`;
        }
    });
}

function toggleAutoTrade() {
    autoTradeEnabled = !autoTradeEnabled;
    const btn = els.autoTradeBtn;
    const dot = btn.querySelector('.status-dot');
    
    if (autoTradeEnabled) {
        btn.style.borderColor = '#238636';
        btn.style.color = '#f0f6fc';
        dot.style.background = '#238636';
        dot.style.boxShadow = '0 0 5px #238636';
    } else {
        btn.style.borderColor = '#30363d';
        btn.style.color = '#8b949e';
        dot.style.background = '#30363d';
        dot.style.boxShadow = 'none';
    }
    console.log("Auto-Trading:", autoTradeEnabled ? "ON" : "OFF");
}

const askRows = [];
const bidRows = [];

// --- Paper Trading Logic ---
async function placeOrder(side, orderType = 'MARKET', quantity = 0.01) {
    let price = 0.0;
    
    // For Limit Orders, calculate Maker price
    if (orderType === 'LIMIT') {
        if (!latestData || !latestData.metrics) {
            console.error("No market data for limit price");
            return;
        }
        // Maker Strategy: Join the Best Bid/Ask
        if (side === 'buy') {
            if (latestData.bids && latestData.bids.length > 0) {
                price = latestData.bids[0][0];
            } else {
                price = latestData.metrics.mid - latestData.metrics.spread/2;
            }
        } else {
            if (latestData.asks && latestData.asks.length > 0) {
                price = latestData.asks[0][0];
            } else {
                price = latestData.metrics.mid + latestData.metrics.spread/2;
            }
        }
    }

    try {
        const res = await fetch('/api/order', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                side: side,
                quantity: quantity,
                order_type: orderType,
                price: price
            })
        });
        const data = await res.json();
        if (data.error) showError(data.error);
        else {
            console.log(`Order Placed: ${side} ${orderType} ${quantity} @ ${price}`);
            // Add Trade Marker only for Market Orders (assumed fill)
            if (orderType === 'MARKET' && midSeries) {
                const now = Math.floor(Date.now() / 1000);
                tradeMarkers.push({
                    time: now,
                    position: side === 'buy' ? 'belowBar' : 'aboveBar',
                    color: side === 'buy' ? '#2ea043' : '#da3633',
                    shape: 'circle',
                    size: 0.5,
                    text: ''
                });
                tradeMarkers.sort((a, b) => a.time - b.time);
                try {
                    midSeries.setMarkers(tradeMarkers);
                } catch(e) { console.error("Marker Error:", e); }
            }
        }
    } catch (e) {
        showError("Order Failed: " + e.message);
    }
}

async function cancelAllOrders() {
    try {
        await fetch('/api/cancel_all', {method: 'POST'});
    } catch (e) {
        console.error("Cancel Failed", e);
    }
}

async function resetAccount() {
    if(!confirm("Reset Paper Trading Account?")) return;
    
    if (autoTradeEnabled) toggleAutoTrade();

    try {
        await fetch('/api/reset', {method: 'POST'});
        showError("Account Reset");
    } catch (e) {
        showError("Reset Failed: " + e.message);
    }
}

// Expose functions to window for HTML onclick
window.placeOrder = placeOrder;
window.resetAccount = resetAccount;

// --- Error Handling ---
function showError(msg) {
    console.error(msg);
    els.errorBanner.textContent = msg;
    els.errorBanner.style.display = 'block';
    setTimeout(() => els.errorBanner.style.display = 'none', 8000);
}

// --- Charting Setup ---
let chart, midSeries, microSeries;

function initChart() {
    try {
        if (typeof LightweightCharts === 'undefined') {
            throw new Error("Lightweight Charts library failed to load. Check connection or ad-blocker.");
        }
        
        chart = LightweightCharts.createChart(document.getElementById('price-chart'), {
            layout: { background: { color: '#161b22' }, textColor: '#8b949e' },
            grid: { vertLines: { color: '#30363d' }, horzLines: { color: '#30363d' } },
            timeScale: { timeVisible: true, secondsVisible: true },
            rightPriceScale: { borderColor: '#30363d' },
        });

        midSeries = chart.addLineSeries({ color: '#2962ff', lineWidth: 2, title: 'Mid' });
        microSeries = chart.addLineSeries({ color: '#e3b341', lineWidth: 2, title: 'Micro' });
    } catch (e) {
        showError("Chart Error: " + e.message);
        document.getElementById('price-chart').innerHTML = 
            '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#da3633;text-align:center;padding:20px;">' +
            'Chart library missing.<br>Trying fallback CDN...<br>Refresh if this persists.</div>';
    }
}

// --- Heatmap Setup ---
const ctx = els.heatmapCanvas.getContext('2d');
let heatmapData = []; // Buffer of snapshots
const MAX_HEATMAP_TICKS = 200;

function resizeCanvas() {
    if (!els.heatmapCanvas) return;
    els.heatmapCanvas.width = els.heatmapCanvas.offsetWidth;
    els.heatmapCanvas.height = els.heatmapCanvas.offsetHeight;
}
window.addEventListener('resize', resizeCanvas);
// Call after delay to ensure layout complete
setTimeout(resizeCanvas, 100);

function createRow(type) {
    const row = document.createElement('div');
    row.className = `row ${type}-row`;
    const price = document.createElement('div'); price.className = 'price';
    const size = document.createElement('div'); size.className = 'size';
    const bar = document.createElement('div'); bar.className = `depth-bar ${type}-bar`;
    row.appendChild(price); row.appendChild(size); row.appendChild(bar);
    return { el: row, price, size, bar };
}

function init() {
    for (let i = 0; i < DEPTH; i++) {
        const rowObj = createRow('ask');
        els.asks.appendChild(rowObj.el);
        askRows.push(rowObj);
    }
    for (let i = 0; i < DEPTH; i++) {
        const rowObj = createRow('bid');
        els.bids.appendChild(rowObj.el);
        bidRows.push(rowObj);
    }
    
    // Short delay to allow script to load if it was deferred or fallback
    setTimeout(initChart, 500);
    
    // Auto-Trade Toggle Listener
    const toggle = document.getElementById('auto-trade-toggle');
    if (toggle) {
        toggle.addEventListener('change', (e) => {
            autoTradeEnabled = e.target.checked;
            console.log("Auto-Trading:", autoTradeEnabled ? "ON" : "OFF");
        });
    }

    // Fee Toggle Listener
    const feesToggle = document.getElementById('fees-toggle');
    if (feesToggle) {
        feesToggle.addEventListener('change', async (e) => {
            const enabled = e.target.checked;
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({fees_enabled: enabled})
                });
                console.log("Fees:", enabled ? "Enabled" : "Disabled");
            } catch (err) {
                console.error("Failed to update settings", err);
                e.target.checked = !enabled; // Revert on error
            }
        });
    }

    connect();
}

function setStatus(type) {
    els.status.className = `status-dot status-${type}`;
    if (type === 'connected') els.statusText.textContent = 'Connected (Real-time)';
    else if (type === 'polling') els.statusText.textContent = 'Polling (Fallback)';
    else els.statusText.textContent = 'Disconnected';
}

function connect() {
    if (isPolling) return;
    try {
        ws = new WebSocket(wsUrl);
        ws.onopen = () => setStatus('connected');
        ws.onmessage = onMessage;
        ws.onclose = () => {
            console.log("WS Disconnected");
            setStatus('disconnected');
            startPolling();
        };
        ws.onerror = (e) => {
            console.error("WS Error", e);
            ws.close();
        };
    } catch (e) {
        console.error("WS Connection Failed", e);
        startPolling();
    }
}

function startPolling() {
    if (isPolling) return;
    isPolling = true;
    setStatus('polling');
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/snapshot');
            if (!response.ok) throw new Error("Fetch failed");
            const data = await response.json();
            updateUI(data);
            setStatus('polling');
        } catch (e) {
            setStatus('disconnected');
        }
    }, 500);
}

function onMessage(event) {
    try {
        const data = JSON.parse(event.data);
        if (data.type !== 'ladder') return;
        updateUI(data);
    } catch (e) {
        console.error("Parse Error", e);
    }
}

function updateUI(data) {
    latestData = data;
    const m = data.metrics;
    const now = Math.floor(Date.now() / 1000);

    // Metrics
    els.spread.textContent = m.spread.toFixed(2);
    els.mid.textContent = m.mid.toFixed(2);
    els.micro.textContent = m.micro.toFixed(2);
    els.imb.textContent = m.imb.toFixed(3);
    els.ofi.textContent = m.ofi.toFixed(4);
    els.cvd.textContent = m.cvd.toFixed(4);
    
    // Colors and Flash Effects
    els.ofi.style.color = m.ofi > 0 ? '#7ee787' : (m.ofi < 0 ? '#ff7b72' : '#f0f6fc');
    
    // Flash Animation for OFI
    if (m.ofi > 5) {
        els.ofi.classList.remove('flash-up', 'flash-down');
        void els.ofi.offsetWidth; // Trigger reflow
        els.ofi.classList.add('flash-up');
    } else if (m.ofi < -5) {
        els.ofi.classList.remove('flash-up', 'flash-down');
        void els.ofi.offsetWidth; // Trigger reflow
        els.ofi.classList.add('flash-down');
    }

    els.cvd.style.color = m.cvd > 0 ? '#7ee787' : (m.cvd < 0 ? '#ff7b72' : '#f0f6fc');
    els.imb.style.color = m.imb > 0 ? '#7ee787' : (m.imb < 0 ? '#ff7b72' : '#f0f6fc');

    // Imbalance Bar
    const bidShare = (m.imb + 1) / 2 * 100;
    els.imbBar.style.width = `${bidShare}%`;
    els.imbBar.style.backgroundColor = m.imb > 0 ? '#238636' : '#da3633';
    els.spreadInfo.textContent = `Spread: ${m.spread.toFixed(2)} | Imb: ${(m.imb * 100).toFixed(1)}%`;

    // Max Volume
    let maxVol = 0;
    for (let i = 0; i < DEPTH; i++) {
        if (data.asks[i]) maxVol = Math.max(maxVol, data.asks[i][1]);
        if (data.bids[i]) maxVol = Math.max(maxVol, data.bids[i][1]);
    }
    if (maxVol === 0) maxVol = 1;

    // Update Rows
    for (let i = 0; i < DEPTH; i++) {
        // Asks
        const askIdx = DEPTH - 1 - i;
        const askItem = data.asks[askIdx];
        const askRow = askRows[i];
        if (askItem) {
            askRow.price.textContent = askItem[0].toFixed(2);
            askRow.size.textContent = askItem[1].toFixed(4);
            askRow.bar.style.width = `${(askItem[1]/maxVol)*100}%`;
        } else {
            askRow.price.textContent = ''; askRow.size.textContent = ''; askRow.bar.style.width = '0';
        }

        // Bids
        const bidItem = data.bids[i];
        const bidRow = bidRows[i];
        if (bidItem) {
            bidRow.price.textContent = bidItem[0].toFixed(2);
            bidRow.size.textContent = bidItem[1].toFixed(4);
            bidRow.bar.style.width = `${(bidItem[1]/maxVol)*100}%`;
        } else {
            bidRow.price.textContent = ''; bidRow.size.textContent = ''; bidRow.bar.style.width = '0';
        }
    }

    // Update Charts
    if (chart && midSeries && microSeries && m.mid && m.micro) {
        midSeries.update({ time: now, value: m.mid });
        microSeries.update({ time: now, value: m.micro });
    }

    // Update Heatmap Data
    try {
        updateHeatmap(data, maxVol);
    } catch (e) {
        console.error("Heatmap Error", e);
    }

    // Update Insights
    try {
        updateInsights(data);
    } catch (e) {
        console.error("Insights Error", e);
    }

    // Update Paper Portfolio
    if (data.portfolio) {
        els.ptUsd.textContent = data.portfolio.usd.toLocaleString('en-US', {style: 'currency', currency: 'USD'});
        els.ptBtc.textContent = data.portfolio.btc.toFixed(4) + " BTC";
        
        // Calculate PnL Color
        const startEquity = 100000;
        const currentEquity = data.portfolio.equity;
        const pnl = currentEquity - startEquity;
        const pnlColor = pnl >= 0 ? '#7ee787' : '#da3633';
        
        els.ptEquity.innerHTML = `${currentEquity.toLocaleString('en-US', {style: 'currency', currency: 'USD'})} <span style="font-size:10px; color:${pnlColor}">(${pnl > 0 ? '+' : ''}${pnl.toFixed(2)})</span>`;
    }
}

function updateInsights(data) {
    const m = data.metrics;
    if (!m) return;

    let sentiment = "Neutral";
    let color = "#8b949e";
    let action = "Wait";
    let reasons = [];

    // Analyze OFI (Order Flow Imbalance)
    if (m.ofi > 5) {
        reasons.push("OFI Buy");
        sentiment = "Bullish";
    } else if (m.ofi < -5) {
        reasons.push("OFI Sell");
        sentiment = "Bearish";
    }

    // Analyze Imbalance
    if (m.imb > 0.3) {
        reasons.push("Bid Support");
        if (sentiment === "Bullish") action = "Buy";
    } else if (m.imb < -0.3) {
        reasons.push("Ask Resist");
        if (sentiment === "Bearish") action = "Sell";
    }

    // Analyze Microprice vs Mid
    const skew = m.micro - m.mid;
    if (Math.abs(skew) > 0.5) {
        reasons.push(`Skew ${skew > 0 ? '+' : '-'}${Math.abs(skew).toFixed(2)}`);
    }

    // Final Decision Logic
    if (sentiment === "Bullish") {
        color = "#7ee787"; // Green
        if (action === "Wait") action = "Watch Buy";
    } else if (sentiment === "Bearish") {
        color = "#ff7b72"; // Red
        if (action === "Wait") action = "Watch Sell";
    }

    // Display - Compact Single Row
    els.insightsText.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-weight:bold; color:${color}; font-size:14px;">${action.toUpperCase()}</span>
                <span style="color:#8b949e; font-size:11px; border-left: 1px solid #30363d; padding-left: 10px;">
                    ${reasons.length > 0 ? reasons.join(' • ') : 'Balanced'}
                </span>
            </div>
            <div style="font-size:11px; color:#58a6ff;">${sentiment}</div>
        </div>
    `;

    // --- Auto-Trading Logic (HFT Maker Strategy) ---
    const now = Date.now();
    if (autoTradeEnabled && (now - lastTradeTime > TRADE_COOLDOWN)) {
        
        // 1. Get current position
        let currentPos = 0.0;
        if (data.portfolio) {
            currentPos = data.portfolio.btc;
        }

        // 2. Define Signal Strength
        const skew = m.micro - m.mid;
        let signal = 0;
        if (Math.abs(skew) > 0.1) signal += skew * 5; 
        if (Math.abs(m.ofi) > 3) signal += m.ofi * 0.1;

        const THRESHOLD = 0.5;

        // Fixed Size
        const size = 0.01;

        // 3. Execution Logic
        if (Math.abs(signal) > THRESHOLD) {
            // Strong Signal -> Taker Trade
            if (signal > 0) {
                // Bullish -> Buy
                if (currentPos < MAX_POSITION) {
                    placeOrder('buy', 'MARKET', size);
                    console.log(`HFT Taker: BUY ${size.toFixed(4)} (Signal: ${signal.toFixed(2)})`);
                }
            } else {
                // Bearish -> Sell
                if (currentPos > -MAX_POSITION) {
                    placeOrder('sell', 'MARKET', size);
                    console.log(`HFT Taker: SELL ${size.toFixed(4)} (Signal: ${signal.toFixed(2)})`);
                }
            }
            lastTradeTime = now;
            
        } else {
            // Neutral -> Inventory Management
            if (Math.abs(currentPos) > 0.1) { // Only if exposure is significant
                // Close position slowly using Market Orders
                if (currentPos > 0) {
                    placeOrder('sell', 'MARKET', 0.01); 
                    console.log("HFT Taker: Unwinding Long");
                } else {
                    placeOrder('buy', 'MARKET', 0.01);
                    console.log("HFT Taker: Unwinding Short");
                }
                lastTradeTime = now;
            }
        }
    }
}

function updateHeatmap(data, maxVol) {
    // Validate Data
    if (!data.metrics || !data.metrics.mid) return;

    // Shift buffer
    heatmapData.push(data);
    if (heatmapData.length > MAX_HEATMAP_TICKS) heatmapData.shift();
    
    // Render
    const w = els.heatmapCanvas.width;
    const h = els.heatmapCanvas.height;
    if (w === 0 || h === 0) return;
    
    ctx.clearRect(0, 0, w, h);
    
    if (heatmapData.length === 0) return;

    // Determine Price Range for Y-axis based on current visible ladder
    const currentMid = data.metrics.mid;
    // if (!currentMid) return; // Already checked above

    // Use a fixed range around mid price for stability, or dynamic based on history
    // Dynamic: Find global min/max in current buffer to avoid "jumping"
    let globalMin = Infinity;
    let globalMax = -Infinity;

    // Optimization: Just check the last few snapshots to keep it responsive but less jumpy
    // Or just use the current snapshot's range with a wider buffer
    // Let's use current snapshot + 0.5% buffer for a "zoom" effect
    const spread = data.metrics.spread || 10;
    const viewRange = spread * 20; // View 20 spreads up and down
    
    const minPrice = currentMid - viewRange;
    const maxPrice = currentMid + viewRange;
    const priceRange = maxPrice - minPrice;
    
    const colWidth = w / MAX_HEATMAP_TICKS;

    // Draw Background Grid
    ctx.strokeStyle = '#21262d';
    ctx.lineWidth = 1;
    ctx.beginPath();
    // Horizontal lines for price levels could go here
    ctx.stroke();

    heatmapData.forEach((snapshot, index) => {
        const x = w - ((heatmapData.length - index) * colWidth);
        
        // Draw Asks (Red)
        snapshot.asks.forEach(([price, qty]) => {
            if (price < minPrice || price > maxPrice) return;
            const y = h - ((price - minPrice) / priceRange) * h;
            // Intensity based on relative volume
            const alpha = Math.min((qty / maxVol) * 1.5, 1); // Boost visibility
            ctx.fillStyle = `rgba(255, 123, 114, ${alpha})`; 
            ctx.fillRect(x, y - 1, colWidth + 0.5, 2); // Slight overlap to avoid gaps
        });

        // Draw Bids (Green)
        snapshot.bids.forEach(([price, qty]) => {
            if (price < minPrice || price > maxPrice) return;
            const y = h - ((price - minPrice) / priceRange) * h;
            const alpha = Math.min((qty / maxVol) * 1.5, 1);
            ctx.fillStyle = `rgba(126, 231, 135, ${alpha})`; 
            ctx.fillRect(x, y - 1, colWidth + 0.5, 2);
        });
    });

    // Draw Mid Price Line
    const midY = h - ((currentMid - minPrice) / priceRange) * h;
    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(w, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Axes Labels
    ctx.fillStyle = "#8b949e";
    ctx.font = "11px 'SF Mono', monospace";
    
    // Y-Axis (Price)
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillText(maxPrice.toFixed(2), w - 5, 5); 
    
    ctx.textBaseline = "bottom";
    ctx.fillText(minPrice.toFixed(2), w - 5, h - 5); 

    // X-Axis (Time)
    ctx.textAlign = "left";
    ctx.fillText("-20s", 5, h - 5);
}

// Initialize on Load
window.addEventListener('DOMContentLoaded', init);