"""
Менеджер для керування ордербуками з різних бірж.
"""
import asyncio
import importlib
import logging
import time
import json
from typing import Dict, List, Any, Optional, Set, Tuple

from config import CUMULATIVE_THRESHOLD
from services.websocket_manager import WebSocketManager
from exchange_clients.base_client import BaseExchangeClient
from exchange_clients.mexc import MEXCClient
from exchange_clients.tradeogre import TradeOgreClient
from exchange_clients.coinex import CoinExClient

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
        self.polling_tasks = {}  # Завдання для polling HTTP бірж
        self.update_stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'last_error': None
        }
    
    async def initialize(self, tokens: List[str], exchanges: List[Dict[str, Any]]):
        """Ініціалізація менеджера ордербуків"""
        self.tokens = tokens
        
        # Ініціалізуємо біржі
        for exchange_data in exchanges:
            try:
                exchange_name = exchange_data["name"]
                exchange_type = exchange_data.get("type", "websocket")
                exchange_url = exchange_data.get("url", "")
                exchange_config = exchange_data.get("config", {})
                
                if exchange_type == "websocket":
                    if exchange_name == "MEXC":
                        client = MEXCClient(exchange_name, exchange_url, exchange_config)
                    elif exchange_name == "CoinEx":
                        client = CoinExClient(exchange_name, exchange_url, exchange_config)
                    else:
                        logger.warning(f"Unknown WebSocket exchange: {exchange_name}")
                        continue
                else:
                    if exchange_name == "TradeOgre":
                        client = TradeOgreClient(exchange_name, exchange_url, exchange_config)
                    else:
                        logger.warning(f"Unknown HTTP exchange: {exchange_name}")
                        continue
                
                # Додаємо токени до клієнта
                for token in tokens:
                    await client.add_token(token)
                
                # Підключаємо клієнта
                await client.connect()
                
                # Зберігаємо клієнта
                self.exchanges[exchange_name] = client
                
                # Запускаємо прослуховування для WebSocket клієнтів
                if exchange_type == "websocket":
                    logger.info(f"Starting WebSocket listener for {exchange_name}")
                    self.listen_tasks[exchange_name] = asyncio.create_task(client.listen())
                
                # Запускаємо polling для HTTP клієнтів
                if exchange_type == "http":
                    logger.info(f"Starting HTTP polling for {exchange_name}")
                    self.polling_tasks[exchange_name] = asyncio.create_task(self._poll_exchange(exchange_name))
                
                logger.info(f"Initialized exchange: {exchange_name}")
                
            except Exception as e:
                logger.error(f"Error initializing exchange {exchange_name}: {str(e)}")
                continue
        
        # Ініціалізуємо структури даних
        for token in tokens:
            self.orderbooks[token] = {}
            self.last_update_time[token] = {}
            
        # Оновлюємо дані
        await self.update_orderbooks()
    
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
            elif name == "CoinEx":
                client = CoinExClient(name, url, config)
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
    
    async def _get_coinex_orderbook(self, client, token: str) -> Optional[dict]:
        """
        Отримання даних ордербуку з CoinEx.
        
        Args:
            client: Клієнт біржі CoinEx
            token: Символ токену
            
        Returns:
            Optional[dict]: Дані ордербуку або None у випадку помилки
        """
        try:
            # Спочатку пробуємо отримати повний ордербук
            if hasattr(client, 'get_orderbook'):
                orderbook = await client.get_orderbook(token)
                if orderbook and isinstance(orderbook, dict):
                    return orderbook
            
            # Якщо не вдалося, пробуємо отримати тільки найкращі ціни
            if hasattr(client, 'get_best_prices'):
                prices = await client.get_best_prices(token)
                if prices and isinstance(prices, dict):
                    return {
                        'best_sell': prices.get('best_sell', 'X X X'),
                        'best_buy': prices.get('best_buy', 'X X X'),
                        'asks': [],
                        'bids': []
                    }
                    
        except Exception as e:
            logger.error(f"CoinEx: помилка отримання даних для {token}: {str(e)}")
            
        return None

    async def _get_standard_orderbook(self, client, token: str) -> Optional[dict]:
        """
        Отримання даних ордербуку зі стандартної біржі.
        
        Args:
            client: Клієнт біржі
            token: Символ токену
            
        Returns:
            Optional[dict]: Дані ордербуку або None у випадку помилки
        """
        try:
            if hasattr(client, 'get_orderbook'):
                orderbook = await client.get_orderbook(token)
                if orderbook:
                    best_sell = orderbook.get('best_sell')
                    best_buy = orderbook.get('best_buy')
                    
                    if best_sell and best_buy:
                        return orderbook
                        
        except Exception as e:
            logger.error(f"Помилка отримання стандартного ордербуку для {token}: {str(e)}")
            
        return None

    def _is_valid_prices(self, best_sell: str, best_buy: str) -> bool:
        """
        Перевірка валідності цін.
        
        Args:
            best_sell: Найкраща ціна продажу
            best_buy: Найкраща ціна купівлі
            
        Returns:
            bool: True якщо ціни валідні, False в іншому випадку
        """
        if not best_sell or not best_buy:
            return False
            
        try:
            sell_price = float(best_sell)
            buy_price = float(best_buy)
            
            # Перевіряємо що ціни більше 0 і ціна продажу більша за ціну купівлі
            return sell_price > 0 and buy_price > 0 and sell_price > buy_price
            
        except (ValueError, TypeError):
            return False

    def _update_orderbook_cache(self, exchange_name: str, token: str, data: dict):
        """
        Оновлення кешу ордербуку.
        
        Args:
            exchange_name (str): Назва біржі
            token (str): Символ токена
            data (dict): Дані ордербуку
        """
        try:
            if token not in self.orderbooks:
                self.orderbooks[token] = {}
            
            if exchange_name not in self.orderbooks[token]:
                self.orderbooks[token][exchange_name] = {}
            
            # Оновлюємо дані
            self.orderbooks[token][exchange_name].update({
                'best_sell': data.get('best_sell', 'X X X'),
                'best_buy': data.get('best_buy', 'X X X')
            })
            
            # Оновлюємо час останнього оновлення
            if token not in self.last_update_time:
                self.last_update_time[token] = {}
            self.last_update_time[token][exchange_name] = time.time()
            
            logger.info(f"Updated orderbook cache for {token} on {exchange_name}")
            logger.info(f"New prices - sell: {data.get('best_sell')}, buy: {data.get('best_buy')}")
            
        except Exception as e:
            logger.error(f"Error updating orderbook cache for {token} on {exchange_name}: {str(e)}")

    async def _broadcast_update(self, exchange_name: str, token: str, data: dict):
        """
        Відправка оновлення через WebSocket.
        
        Args:
            exchange_name (str): Назва біржі
            token (str): Символ токена
            data (dict): Дані для оновлення
        """
        try:
            # Оновлюємо кеш
            self._update_orderbook_cache(exchange_name, token, data)
            
            # Формуємо дані для відправки
            update_data = {
                'exchange': exchange_name,
                'token': token,
                'best_sell': data.get('best_sell', 'X X X'),
                'best_buy': data.get('best_buy', 'X X X')
            }
            
            # Відправляємо оновлення
            await self.websocket_manager.broadcast(update_data)
            logger.info(f"Broadcasted price update for {token} on {exchange_name}")
            logger.info(f"Data being sent: {json.dumps(update_data, indent=2, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"Error broadcasting update for {token} on {exchange_name}: {str(e)}")

    async def _handle_error(self, exchange_name: str, token: str, error: Exception):
        """
        Обробка помилок оновлення ордербуку.
        
        Args:
            exchange_name: Назва біржі
            token: Символ токену
            error: Об'єкт помилки
        """
        # Логуємо помилки тільки для CoinEx, для інших бірж просто оновлюємо статистику
        if exchange_name == "CoinEx":
            logger.error(f"Помилка оновлення ордербуку для {token} на {exchange_name}: {str(error)}")
        
        self.update_stats['failed_updates'] += 1
        self.update_stats['last_error'] = str(error)
        
        # Встановлюємо значення за замовчуванням
        if token not in self.orderbooks:
            self.orderbooks[token] = {}
        if exchange_name not in self.orderbooks[token]:
            self.orderbooks[token][exchange_name] = {
                'best_sell': 'X X X',
                'best_buy': 'X X X',
                'asks': [],
                'bids': [],
                'error': str(error),
                'error_timestamp': time.time()
            }

    async def update_orderbooks(self):
        """Оновлення ордербуків для всіх токенів на всіх біржах"""
        self.update_stats['total_updates'] += 1
        current_time = time.time()
        
        for exchange_name, client in self.exchanges.items():
            for token in self.tokens:
                try:
                    # Перевіряємо час останнього оновлення
                    last_update = self.last_update_time.get(token, {}).get(exchange_name, 0)
                    if current_time - last_update < 1:  # Пропускаємо якщо пройшло менше 1 секунди
                        continue
                        
                    # Отримуємо дані ордербуку
                    orderbook_data = None
                    if exchange_name == "CoinEx":
                        orderbook_data = await self._get_coinex_orderbook(client, token)
                    elif exchange_name == "TradeOgre":
                        orderbook_data = await self._get_tradeogre_orderbook(client, token)
                    else:
                        orderbook_data = await self._get_standard_orderbook(client, token)
                        
                    if orderbook_data:
                        best_sell = orderbook_data.get('best_sell')
                        best_buy = orderbook_data.get('best_buy')
                        
                        # Перевіряємо чи змінилися ціни
                        current_data = self.orderbooks.get(token, {}).get(exchange_name, {})
                        current_sell = current_data.get('best_sell')
                        current_buy = current_data.get('best_buy')
                        
                        if (best_sell != current_sell or best_buy != current_buy) and self._is_valid_prices(best_sell, best_buy):
                            # Оновлюємо кеш
                            self._update_orderbook_cache(exchange_name, token, orderbook_data)
                            
                            # Відправляємо оновлення
                            await self._broadcast_update(exchange_name, token, orderbook_data)
                            
                            self.update_stats['successful_updates'] += 1
                            logger.info(f"Updated prices for {token} on {exchange_name}: sell={best_sell}, buy={best_buy}")
                        
                except Exception as e:
                    await self._handle_error(exchange_name, token, e)
                    
        await asyncio.sleep(0.1)  # Невелика затримка між циклами
    
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
            logger.info(f"Запит ордербуку для {token} на {exchange}")
            
            orderbook_data = await client.get_orderbook(token)
            logger.info(f"Отримані дані ордербуку для {token} на {exchange}: {json.dumps(orderbook_data, indent=2, ensure_ascii=False)}")
            
            if not orderbook_data:
                logger.warning(f"Немає даних ордербуку для {token} на {exchange}")
                return {
                    "asks": [],
                    "bids": []
                }
                
            asks = orderbook_data.get('asks', [])
            bids = orderbook_data.get('bids', [])
            
            logger.info(f"Форматовані дані для {token} на {exchange}:")
            logger.info(f"asks: {json.dumps(asks[:5], indent=2)}")
            logger.info(f"bids: {json.dumps(bids[:5], indent=2)}")
            
            return {
                "asks": asks,
                "bids": bids
            }
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {token} on {exchange}: {str(e)}")
            return {
                "asks": [],
                "bids": []
            }

    async def _get_tradeogre_orderbook(self, client, token: str) -> Dict[str, Any]:
        """
        Отримання даних ордербуку для TradeOgre.
        
        Args:
            client: Клієнт TradeOgre
            token (str): Символ токена
            
        Returns:
            Dict[str, Any]: Дані ордербуку
        """
        try:
            # Отримуємо дані через REST API
            orderbook = await client.get_orderbook(token)
            if not orderbook:
                logger.warning(f"TradeOgre: No orderbook data for {token}")
                return None
                
            # Форматуємо дані
            asks = orderbook.get('asks', [])
            bids = orderbook.get('bids', [])
            
            if not asks or not bids:
                logger.warning(f"TradeOgre: Empty orderbook for {token}")
                return None
                
            # Отримуємо найкращі ціни
            best_sell = orderbook.get('best_sell')
            best_buy = orderbook.get('best_buy')
            
            if not best_sell or not best_buy:
                logger.warning(f"TradeOgre: Missing best prices for {token}")
                return None
                
            return {
                'asks': asks,
                'bids': bids,
                'best_sell': best_sell,
                'best_buy': best_buy
            }
            
        except Exception as e:
            logger.error(f"Error getting TradeOgre orderbook for {token}: {str(e)}")
            return None