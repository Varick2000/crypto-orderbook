"""
Менеджер для керування ордербуками з різних бірж.
"""
import asyncio
import importlib
import logging
import time
from typing import Dict, List, Any, Optional, Set, Tuple

from config import CUMULATIVE_THRESHOLD
from services.websocket_manager import WebSocketManager
from exchange_clients.base_client import BaseExchangeClient
from exchange_clients.mexc import MEXCClient
from exchange_clients.tradeogre import TradeOgreClient

# Налаштування логгера
logger = logging.getLogger(__name__)


class OrderbookManager:
    """
    Менеджер для керування ордербуками з різних бірж.
    """
    
    def __init__(self, websocket_manager: WebSocketManager):
        """
        Ініціалізація менеджера ордербуків.
        
        Args:
            websocket_manager (WebSocketManager): Менеджер WebSocket-з'єднань з клієнтами
        """
        self.websocket_manager = websocket_manager
        self.exchanges: Dict[str, BaseExchangeClient] = {}
        self.tokens: List[str] = []
        self.orderbooks: Dict[str, Dict[str, Dict[str, Any]]] = {}  # {token: {exchange: {'best_sell': '...', 'best_buy': '...'}}}
        self.polling_task = None
        self.last_update_time: Dict[str, Dict[str, float]] = {}  # {token: {exchange: timestamp}}
        self.listen_tasks = {}  # Завдання для прослуховування WebSocket
    
    async def initialize(self, tokens: List[str], exchanges: List[Dict[str, Any]]):
        """
        Ініціалізація менеджера ордербуків.
        
        Args:
            tokens (List[str]): Список токенів
            exchanges (List[Dict[str, Any]]): Список бірж
        """
        self.tokens = tokens
        
        # Ініціалізація клієнтів бірж
        for exchange_data in exchanges:
            await self.add_exchange(exchange_data)
            
        # Ініціалізація структури ордербуків
        for token in self.tokens:
            if token not in self.orderbooks:
                self.orderbooks[token] = {}
                self.last_update_time[token] = {}
                
            for exchange_name in self.exchanges:
                self.orderbooks[token][exchange_name] = {
                    'best_sell': 'X X X',
                    'best_buy': 'X X X'
                }
                self.last_update_time[token][exchange_name] = 0
    
    async def add_exchange(self, exchange_data: Dict[str, Any]):
        """
        Додавання нової біржі.
        
        Args:
            exchange_data (Dict[str, Any]): Дані біржі
        """
        name = exchange_data.get('name')
        url = exchange_data.get('url')
        client_type = exchange_data.get('type', 'websocket')
        config = exchange_data.get('config', {})
        
        if name in self.exchanges:
            logger.warning(f"Exchange {name} already exists")
            return
            
        try:
            # Явне створення клієнтів за типом біржі
            client = None
            
            if name == "MEXC":
                client = MEXCClient(name, url, config)
            elif name == "TradeOgre":
                client = TradeOgreClient(name, url, config)
            else:
                logger.warning(f"Unknown exchange type: {name}, using base client")
                if client_type == "websocket":
                    from exchange_clients.websocket_client import WebSocketExchangeClient
                    client = WebSocketExchangeClient(name, url, config)
                else:
                    from exchange_clients.http_client import HttpExchangeClient
                    client = HttpExchangeClient(name, url, config)
            
            # Додаємо токени до клієнта
            for token in self.tokens:
                await client.add_token(token)
                
                # Ініціалізуємо запис для цієї біржі в ордербуках
                if token in self.orderbooks:
                    self.orderbooks[token][name] = {
                        'best_sell': 'X X X',
                        'best_buy': 'X X X'
                    }
                    self.last_update_time[token][name] = 0
            
            # Підключаємо клієнта
            await client.connect()
            
            # Додаємо клієнта до списку
            self.exchanges[name] = client
            
            # Запускаємо прослуховування для WebSocket клієнтів
            if hasattr(client, 'listen'):
                self.listen_tasks[name] = asyncio.create_task(client.listen())
            
            # Запускаємо polling для HTTP клієнтів
            if client_type == 'http':
                self.polling_tasks[name] = asyncio.create_task(self._poll_exchange(name))
            
            logger.info(f"Added exchange {name}")
            
        except Exception as e:
            logger.error(f"Error adding exchange {name}: {str(e)}")
    
    async def _poll_exchange(self, exchange_name: str):
        """Оновлення даних для конкретної біржі."""
        while True:
            try:
                await self.update_orderbooks()
                await asyncio.sleep(1)  # Оновлюємо кожну секунду
            except Exception as e:
                logger.error(f"Error polling exchange {exchange_name}: {str(e)}")
                await asyncio.sleep(1)  # Чекаємо перед повторною спробою
    
    async def remove_exchange(self, exchange_name: str):
        """
        Видалення біржі.
        
        Args:
            exchange_name (str): Назва біржі
        """
        if exchange_name not in self.exchanges:
            logger.warning(f"Exchange {exchange_name} not found")
            return
            
        try:
            # Зупиняємо прослуховування
            if exchange_name in self.listen_tasks:
                self.listen_tasks[exchange_name].cancel()
                del self.listen_tasks[exchange_name]
            
            # Відключаємо клієнта
            await self.exchanges[exchange_name].close()
            
            # Видаляємо клієнта зі списку
            del self.exchanges[exchange_name]
            
            # Видаляємо запис для цієї біржі з ордербуків
            for token in self.orderbooks:
                if exchange_name in self.orderbooks[token]:
                    del self.orderbooks[token][exchange_name]
                
                if token in self.last_update_time and exchange_name in self.last_update_time[token]:
                    del self.last_update_time[token][exchange_name]
            
            logger.info(f"Removed exchange {exchange_name}")
            
        except Exception as e:
            logger.error(f"Error removing exchange {exchange_name}: {str(e)}")
    
    async def add_token(self, token: str):
        """
        Додавання нового токена.
        
        Args:
            token (str): Символ токена
        """
        if token in self.tokens:
            logger.warning(f"Token {token} already exists")
            return
            
        try:
            # Додаємо токен до списку
            self.tokens.append(token)
            
            # Ініціалізуємо запис для цього токена в ордербуках
            if token not in self.orderbooks:
                self.orderbooks[token] = {}
                self.last_update_time[token] = {}
                
            # Додаємо токен до всіх клієнтів бірж
            for exchange_name, client in self.exchanges.items():
                await client.add_token(token)
                self.orderbooks[token][exchange_name] = {
                    'best_sell': 'X X X',
                    'best_buy': 'X X X'
                }
                self.last_update_time[token][exchange_name] = 0
            
            logger.info(f"Added token {token}")
            
        except Exception as e:
            logger.error(f"Error adding token {token}: {str(e)}")
    
    async def remove_token(self, token: str):
        """
        Видалення токена.
        
        Args:
            token (str): Символ токена
        """
        if token not in self.tokens:
            logger.warning(f"Token {token} not found")
            return
            
        try:
            # Видаляємо токен зі списку
            self.tokens.remove(token)
            
            # Видаляємо токен з усіх клієнтів бірж
            for exchange_name, client in self.exchanges.items():
                await client.remove_token(token)
            
            # Видаляємо запис для цього токена з ордербуків
            if token in self.orderbooks:
                del self.orderbooks[token]
                
            if token in self.last_update_time:
                del self.last_update_time[token]
            
            logger.info(f"Removed token {token}")
            
        except Exception as e:
            logger.error(f"Error removing token {token}: {str(e)}")
    
    async def update_orderbooks(self):
        """Оновлення ордербуків для всіх токенів на всіх біржах"""
        for exchange_name, client in self.exchanges.items():
            for token in self.tokens:
                try:
                    logger.info(f"Updating orderbook for {token} on {exchange_name}")
                    best_sell, best_buy = client.get_best_prices(token)
                    logger.info(f"Received orderbook data for {token} on {exchange_name}: sell={best_sell}, buy={best_buy}")
                    
                    if not self.orderbooks.get(token):
                        self.orderbooks[token] = {}
                    if not self.orderbooks[token].get(exchange_name):
                        self.orderbooks[token][exchange_name] = {}
                        
                    self.orderbooks[token][exchange_name] = {
                        'best_sell': best_sell,
                        'best_buy': best_buy
                    }
                    
                    await self.websocket_manager.broadcast_orderbook_update(
                        exchange_name,
                        token,
                        best_sell,
                        best_buy
                    )
                except Exception as e:
                    logger.error(f"Error updating orderbook for {token} on {exchange_name}: {str(e)}")
    
    async def start_polling(self):
        """Запуск періодичного оновлення ордербуків."""
        while True:
            await self.update_orderbooks()
            await asyncio.sleep(1)  # Оновлюємо кожну секунду
    
    async def close_all_connections(self):
        """Закриття всіх з'єднань."""
        # Зупиняємо всі завдання прослуховування
        for task in self.listen_tasks.values():
            task.cancel()
        self.listen_tasks.clear()
        
        # Закриваємо всі з'єднання
        for exchange_name, client in self.exchanges.items():
            try:
                await client.close()
            except Exception as e:
                logger.error(f"Error closing connection for {exchange_name}: {str(e)}")
    
    def get_all_orderbooks(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Отримання всіх ордербуків."""
        return self.orderbooks

    async def get_orderbook(self, token: str, exchange: str) -> Optional[Dict[str, List[Dict[str, str]]]]:
        """Отримання даних ордербуку для конкретного токена на біржі."""
        if exchange not in self.exchanges:
            logger.error(f"Exchange {exchange} not found")
            return None
            
        try:
            # Отримуємо дані ордербуку від клієнта біржі
            client = self.exchanges[exchange]
            orderbook_data = await client.get_orderbook(token)
            
            if not orderbook_data:
                return None
                
            return {
                "asks": orderbook_data.get('asks', []),
                "bids": orderbook_data.get('bids', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {token} on {exchange}: {str(e)}")
            return None