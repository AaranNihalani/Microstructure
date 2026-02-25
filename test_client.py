import asyncio
import websockets
import json
import time

async def test_client():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        count = 0
        start_time = time.time()
        
        while count < 5:
            message = await websocket.recv()
            data = json.loads(message)
            
            print(f"Received payload: {json.dumps(data, indent=2)}")
            
            # Verify structure
            assert data["type"] == "ladder"
            assert "bids" in data
            assert "asks" in data
            assert "metrics" in data
            
            m = data["metrics"]
            assert "imb" in m
            assert "spread" in m
            assert "mid" in m
            assert "micro" in m
            assert "ofi" in m
            assert "cvd" in m
            
            # Verify Bids order (Descending)
            bids = data["bids"]
            if len(bids) > 1:
                assert bids[0][0] >= bids[1][0], "Bids not sorted descending"
                
            # Verify Asks order (Ascending)
            asks = data["asks"]
            if len(asks) > 1:
                assert asks[0][0] <= asks[1][0], "Asks not sorted ascending"
                
            count += 1
            
        end_time = time.time()
        duration = end_time - start_time
        print(f"Received 5 messages in {duration:.4f} seconds (Avg: {duration/5:.4f}s)")

if __name__ == "__main__":
    asyncio.run(test_client())
