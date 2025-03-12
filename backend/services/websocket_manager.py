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
        
        # Статистика відправки повідомлень
        self.stats = {
            'total_messages': 0,
            'successful_sends': 0,
            'failed_sends': 0,
            'success_rate': 0
        }
    
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
        """Відправка повідомлення всім підключеним клієнтам"""
        if not self.active_connections:
            logger.warning("Немає активних підключень для відправки оновлення")
            return
       
        # Додаємо додаткове логування для відстеження оновлень CoinEx
        if message.get("type") == "orderbook_update" and message.get("exchange") == "CoinEx":
            logger.info(f"WebSocketManager: відправка оновлення CoinEx для {message.get('token')}: sell={message.get('best_sell')}, buy={message.get('best_buy')}")
        
        # Формуємо JSON-рядок для відправки один раз
        try:
            message_json = json.dumps(message)
        except Exception as e:
            logger.error(f"Error serializing message to JSON: {str(e)}")
            return
       
        # Відправляємо повідомлення всім клієнтам
        successful_sends = 0
        failures = 0
        failed_connections = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
                successful_sends += 1
            except Exception as e:
                failures += 1
                failed_connections.append(connection)
                logger.error(f"Error sending message to client: {str(e)}")
            
        # Логуємо результат відправки
        if message.get("type") == "orderbook_update":
            logger.info(f"Broadcast result: {successful_sends} successful, {failures} failed")
        
        # Відключаємо клієнтів з помилками
        for connection in failed_connections:
            try:
                await self.disconnect(connection)
                logger.info("Successfully disconnected failed client")
            except Exception as e:
                logger.error(f"Error disconnecting client: {str(e)}")
            
        # Оновлюємо статистику
        self._update_stats(successful_sends, failures)
    
    def _update_stats(self, successful_sends: int, failures: int):
        """Оновлення статистики відправки повідомлень"""
        self.stats['total_messages'] += successful_sends + failures
        self.stats['successful_sends'] += successful_sends
        self.stats['failed_sends'] += failures
        self.stats['success_rate'] = (self.stats['successful_sends'] / self.stats['total_messages'] * 100) if self.stats['total_messages'] > 0 else 0
    
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