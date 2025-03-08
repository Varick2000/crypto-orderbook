"""
Модуль для управління WebSocket-з'єднаннями з клієнтами.
"""
import json
import logging
from typing import Dict, List, Set, Any, Optional

from fastapi import WebSocket

# Налаштування логгера
logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Менеджер для керування WebSocket-підключеннями клієнтів.
    """
    
    def __init__(self):
        # Активні з'єднання з клієнтами
        self.active_connections: List[WebSocket] = []
        
        # Підписки клієнтів на токени та біржі
        # {client_id: {'tokens': ['BTC', 'ETH'], 'exchanges': ['MEXC', 'CoinEx']}}
        self.subscriptions: Dict[int, Dict[str, List[str]]] = {}
    
    async def connect(self, websocket: WebSocket):
        """
        Додати нове WebSocket з'єднання.
        """
        # Примітка: НЕ викликаємо accept тут - він повинен бути викликаний у app.py
        self.active_connections.append(websocket)
        self.subscriptions[id(websocket)] = {'tokens': [], 'exchanges': []}
        logger.info(f"Client connected: {id(websocket)}")
    
    async def disconnect(self, websocket: WebSocket):
        """
        Видалити WebSocket з'єднання.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if id(websocket) in self.subscriptions:
            del self.subscriptions[id(websocket)]
            
        logger.info(f"Client disconnected: {id(websocket)}")
    
    async def subscribe(self, websocket: WebSocket, tokens: List[str], exchanges: List[str]):
        """
        Підписати клієнта на конкретні токени та біржі.
        """
        client_id = id(websocket)
        
        # Якщо обидва списки порожні - клієнт хоче отримувати всі дані
        if not tokens and not exchanges:
            self.subscriptions[client_id] = {'tokens': [], 'exchanges': []}
            return
        
        if client_id in self.subscriptions:
            if tokens:
                self.subscriptions[client_id]['tokens'] = tokens
            if exchanges:
                self.subscriptions[client_id]['exchanges'] = exchanges
                
            logger.info(f"Client {client_id} subscribed to tokens: {tokens}, exchanges: {exchanges}")
    
    async def unsubscribe(self, websocket: WebSocket):
        """
        Видалити всі підписки клієнта.
        """
        client_id = id(websocket)
        if client_id in self.subscriptions:
            self.subscriptions[client_id] = {'tokens': [], 'exchanges': []}
            logger.info(f"Client {client_id} unsubscribed from all")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        Надіслати повідомлення конкретному клієнту.
        """
        await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Надіслати повідомлення всім підключеним клієнтам.
        """
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to client {id(connection)}: {str(e)}")
                # Якщо сталася помилка, можливо клієнт відключився
                await self.disconnect(connection)
    
    async def broadcast_orderbook_update(self, exchange: str, token: str, best_sell: str, best_buy: str):
        """
        Відправка оновлення ордербуку всім підписаним клієнтам.
        """
        message = {
            "type": "orderbook_update",
            "exchange": exchange,
            "token": token,
            "best_sell": best_sell,
            "best_buy": best_buy
        }
        await self.broadcast(message)