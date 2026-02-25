import asyncio
from typing import List
from fastapi import WebSocket, WebSocketDisconnect
from .engine import OrderBook

class Broadcaster:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Create a list of tasks for broadcasting to avoid blocking
        # However, sending to many clients might be slow.
        # For now, simple iteration.
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle disconnection or error silently
                # In a real app, we might want to clean up here too
                pass

    async def start_broadcasting(self, order_book: OrderBook, paper_engine=None):
        """
        Background task to broadcast ladder payload every 100ms.
        """
        while True:
            try:
                await asyncio.sleep(0.1)  # 100ms
                if not self.active_connections:
                    continue
                
                payload = order_book.ladder_payload(depth=10)
                
                if paper_engine:
                    current_price = payload.get("metrics", {}).get("mid", 0.0)
                    payload["portfolio"] = paper_engine.get_portfolio_snapshot(current_price)
                
                await self.broadcast(payload)
                
            except Exception as e:
                # Log error but keep running
                print(f"Broadcaster error: {e}")
                await asyncio.sleep(1)
