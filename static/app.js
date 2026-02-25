const DEPTH = 10;
const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + "/ws";
let ws;
let pollingInterval;
let isPolling = false;

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
    spreadInfo: document.getElementById('spread-info'),
    status: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text'),
    heatmapCanvas: document.getElementById('heatmap-canvas'),
    errorBanner: document.getElementById('error-banner'),
    insightsText: document.getElementById('insights-text')
};

const askRows = [];
const bidRows = [];

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
    const m = data.metrics;
    const now = Math.floor(Date.now() / 1000);

    // Metrics
    els.spread.textContent = m.spread.toFixed(2);
    els.mid.textContent = m.mid.toFixed(2);
    els.micro.textContent = m.micro.toFixed(2);
    els.imb.textContent = m.imb.toFixed(3);
    els.ofi.textContent = m.ofi.toFixed(4);
    els.cvd.textContent = m.cvd.toFixed(4);
    
    // Colors
    els.ofi.style.color = m.ofi > 0 ? '#7ee787' : (m.ofi < 0 ? '#ff7b72' : '#f0f6fc');
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
}

function updateHeatmap(data, maxVol) {
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
    // Use the lowest bid and highest ask from the current depth to frame the heatmap
    const currentMid = data.metrics.mid;
    if (!currentMid) return;

    // Find min/max from current ladder snapshot
    let minP = currentMid;
    let maxP = currentMid;
    
    if (data.bids.length > 0) {
        // bids are sorted descending, so last element is lowest price
        minP = data.bids[data.bids.length - 1][0];
    }
    if (data.asks.length > 0) {
        // asks are sorted ascending, so last element is highest price
        maxP = data.asks[data.asks.length - 1][0];
    }

    // Add a small buffer (5%)
    const buffer = (maxP - minP) * 0.05;
    const minPrice = minP - buffer;
    const maxPrice = maxP + buffer;
    const priceRange = maxPrice - minPrice;
    
    if (priceRange <= 0) return; // Safety check

    const colWidth = w / MAX_HEATMAP_TICKS;

    heatmapData.forEach((snapshot, index) => {
        const x = w - ((heatmapData.length - index) * colWidth);
        
        // Draw Asks
        snapshot.asks.forEach(([price, qty]) => {
            if (price < minPrice || price > maxPrice) return;
            const y = h - ((price - minPrice) / priceRange) * h;
            const alpha = Math.min(qty / maxVol, 1);
            ctx.fillStyle = `rgba(255, 123, 114, ${alpha})`; // Red
            ctx.fillRect(x, y, colWidth, 2);
        });

        // Draw Bids
        snapshot.bids.forEach(([price, qty]) => {
            if (price < minPrice || price > maxPrice) return;
            const y = h - ((price - minPrice) / priceRange) * h;
            const alpha = Math.min(qty / maxVol, 1);
            ctx.fillStyle = `rgba(126, 231, 135, ${alpha})`; // Green
            ctx.fillRect(x, y, colWidth, 2);
        });
    });

    // Draw Axes Labels
    ctx.fillStyle = "#8b949e";
    ctx.font = "10px monospace";
    
    // Y-Axis (Price) - Right aligned
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillText(maxPrice.toFixed(2), w - 5, 5); // Top
    
    ctx.textBaseline = "middle";
    ctx.fillText(currentMid.toFixed(2), w - 5, h / 2); // Mid
    
    ctx.textBaseline = "bottom";
    ctx.fillText(minPrice.toFixed(2), w - 5, h - 5); // Bottom

    // X-Axis (Time) - Left aligned
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText("-20s", 5, h - 5);
    
    ctx.textAlign = "center";
    ctx.fillText("-10s", w / 2, h - 5);
    
    ctx.textAlign = "right";
    ctx.fillText("Now", w - 35, h - 5); // Offset from price label
}

// Initialize on Load
window.addEventListener('DOMContentLoaded', init);
