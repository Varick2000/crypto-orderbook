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
from exchange_clients.xeggex import XeggexClient

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
        self.connected_clients = set()  # Множина підключених WebSocket клієнтів
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
                    elif exchange_name == "Xeggex":
                        client = XeggexClient(exchange_name, exchange_url, exchange_config)
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
                if hasattr(client, 'listen') and exchange_name != "Xeggex":
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
            elif name == "Xeggex":
                client = XeggexClient(name, url, config)
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
            if hasattr(client, 'listen') and name != "Xeggex":
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
    
    async def _get_coinex_orderbook(self, client, token: str) -> Dict[str, Any]:
        """
        Отримання даних ордербуку для CoinEx.
        
        Args:
            client: Клієнт CoinEx
            token (str): Символ токена
            
        Returns:
            Dict[str, Any]: Дані ордербуку
        """
        try:
            # Отримуємо дані через REST API
            orderbook = await client.get_orderbook(token)
            if not orderbook:
                logger.warning(f"CoinEx: No orderbook data for {token}")
                return None
                
            # Форматуємо дані
            asks = orderbook.get('asks', [])
            bids = orderbook.get('bids', [])
            
            if not asks or not bids:
                logger.warning(f"CoinEx: Empty orderbook for {token}")
                return None
                
            # Отримуємо найкращі ціни
            best_sell = orderbook.get('best_sell')
            best_buy = orderbook.get('best_buy')
            
            if not best_sell or not best_buy:
                logger.warning(f"CoinEx: Missing best prices for {token}")
                return None
                
            return {
                'asks': asks,
                'bids': bids,
                'best_sell': best_sell,
                'best_buy': best_buy
            }
            
        except Exception as e:
            logger.error(f"Error getting CoinEx orderbook for {token}: {str(e)}")
            return None

    async def _get_standard_orderbook(self, client, token: str) -> Dict[str, Any]:
        """
        Отримання даних ордербуку в стандартному форматі.
        
        Args:
            client: Клієнт біржі
            token (str): Символ токена
            
        Returns:
            Dict[str, Any]: Дані ордербуку
        """
        try:
            # Отримуємо дані ордербуку
            orderbook_data = await client.get_orderbook(token)
            if not orderbook_data:
                logger.warning(f"No orderbook data received for {token}")
                return None
                
            # Перевіряємо наявність необхідних полів
            if not isinstance(orderbook_data, dict):
                logger.warning(f"Invalid orderbook data format for {token}")
                return None
                
            # Отримуємо asks та bids
            asks = orderbook_data.get('asks', [])
            bids = orderbook_data.get('bids', [])
            
            if not asks or not bids:
                logger.warning(f"Empty orderbook for {token}")
                return None
                
            # Отримуємо найкращі ціни
            best_sell = asks[0][0] if asks else None
            best_buy = bids[0][0] if bids else None
            
            if not best_sell or not best_buy:
                logger.warning(f"Missing best prices for {token}")
                return None
                
            # Форматуємо дані
            formatted_data = {
                'asks': asks,
                'bids': bids,
                'best_sell': best_sell,
                'best_buy': best_buy
            }
            
            logger.info(f"Formatted orderbook data for {token}: sell={best_sell}, buy={best_buy}")
            return formatted_data
            
        except Exception as e:
            logger.error(f"Error getting standard orderbook for {token}: {str(e)}")
            return None

    def _is_valid_prices(self, best_sell: Any, best_buy: Any) -> bool:
        """
        Перевірка валідності цін.
        
        Args:
            best_sell: Найкраща ціна продажу
            best_buy: Найкраща ціна покупки
            
        Returns:
            bool: True якщо ціни валідні, False в іншому випадку
        """
        try:
            # Перевіряємо на None або пусті значення
            if best_sell is None or best_buy is None:
                return False
                
            # Перевіряємо на плейсхолдер
            if best_sell == 'X X X' or best_buy == 'X X X':
                return False
                
            # Перевіряємо на числові значення
            sell_price = float(best_sell)
            buy_price = float(best_buy)
            
            # Перевіряємо на позитивні значення
            if sell_price <= 0 or buy_price <= 0:
                return False
                
            # Перевіряємо на розумну різницю між цінами
            if sell_price < buy_price:
                return False
                
            return True
            
        except (ValueError, TypeError):
            return False

    def _update_orderbook_cache(self, exchange: str, token: str, data: Dict[str, Any]):
        """
        Оновлення кешу ордербуку.
        
        Args:
            exchange (str): Назва біржі
            token (str): Символ токена
            data (Dict[str, Any]): Дані ордербуку
        """
        try:
            if not data or not isinstance(data, dict):
                logger.warning(f"Invalid orderbook data for {token} on {exchange}")
                return
                
            # Спеціальна обробка для Xeggex
            if exchange == "Xeggex":
                logger.info(f"Оновлення кешу ордербуку для {token} на {exchange}")
                asks = data.get('asks', [])
                bids = data.get('bids', [])
                
                logger.info(f"Кількість asks: {len(asks)}, bids: {len(bids)}")
                logger.info(f"Xeggex data in _update_orderbook_cache: asks={asks}, bids={bids}")
                
                if not asks or not bids:
                    logger.warning(f"Empty orderbook for {token} on Xeggex")
                    return
                    
                best_sell = asks[0]['price'] if asks else None
                best_buy = bids[0]['price'] if bids else None
                
                logger.info(f"Найкращі ціни для {token}: sell={best_sell}, buy={best_buy}")
                logger.info(f"Типи даних: sell={type(best_sell)}, buy={type(best_buy)}")
                logger.info(f"Повні дані asks[0]: {json.dumps(asks[0], indent=2)}")
                logger.info(f"Повні дані bids[0]: {json.dumps(bids[0], indent=2)}")
                
                if not best_sell or not best_buy:
                    logger.warning(f"Missing best prices for {token} on Xeggex")
                    return
                    
                # Оновлюємо кеш
                self.orderbooks[token][exchange] = {
                    'asks': asks,
                    'bids': bids,
                    'best_sell': best_sell,
                    'best_buy': best_buy
                }
                self.last_update_time[token][exchange] = time.time()
                
                # Відправляємо оновлення
                asyncio.create_task(self._broadcast_update(exchange, token, {
                    'best_sell': best_sell,
                    'best_buy': best_buy
                }))
            else:
                # Стандартна обробка для інших бірж
                best_sell = data.get('best_sell')
                best_buy = data.get('best_buy')
                
                if best_sell and best_buy:
                    self.orderbooks[token][exchange] = {
                        'asks': data.get('asks', []),
                        'bids': data.get('bids', []),
                        'best_sell': best_sell,
                        'best_buy': best_buy
                    }
                    self.last_update_time[token][exchange] = time.time()
                    
                    # Відправляємо оновлення
                    asyncio.create_task(self._broadcast_update(exchange, token, data))
                    
        except Exception as e:
            logger.error(f"Error updating orderbook cache for {token} on {exchange}: {str(e)}")

    async def _broadcast_update(self, exchange: str, token: str, data: Dict[str, Any]):
        """Відправка оновлення ордербуку всім підключеним клієнтам."""
        try:
            # Форматуємо дані для відправки
            if exchange == "Xeggex":
                # Для Xeggex використовуємо спеціальний формат
                message = {
                    "type": "orderbook_update",
                    "exchange": exchange,
                    "token": token,
                    "data": {
                        "best_sell": data.get('best_sell'),
                        "best_buy": data.get('best_buy')
                    }
                }
            else:
                # Для інших бірж використовуємо стандартний формат
                message = {
                    "type": "orderbook_update",
                    "exchange": exchange,
                    "token": token,
                    "data": {
                        "asks": data.get('asks', []),
                        "bids": data.get('bids', []),
                        "best_sell": data.get('best_sell'),
                        "best_buy": data.get('best_buy')
                    }
                }
            
            # Відправляємо оновлення всім підключеним клієнтам
            for websocket in self.connected_clients:
                try:
                    await websocket.send(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending update to client: {str(e)}")
                    await self._remove_client(websocket)
                    
        except Exception as e:
            logger.error(f"Error broadcasting update: {str(e)}")

    async def _handle_error(self, exchange: str, token: str, error: Exception):
        """
        Обробка помилок при оновленні ордербуку.
        
        Args:
            exchange (str): Назва біржі
            token (str): Символ токена
            error (Exception): Об'єкт помилки
        """
        try:
            # Логуємо помилку
            logger.error(f"Error updating orderbook for {token} on {exchange}: {str(error)}")
            
            # Оновлюємо статистику
            self.update_stats['failed_updates'] += 1
            
            # Відправляємо повідомлення про помилку
            error_message = {
                "type": "error",
                "exchange": exchange,
                "token": token,
                "message": str(error)
            }
            
            # Відправляємо повідомлення всім підключеним клієнтам
            for websocket in self.connected_clients:
                try:
                    await websocket.send(json.dumps(error_message))
                except Exception as e:
                    logger.error(f"Error sending error message to client: {str(e)}")
                    await self._remove_client(websocket)
                    
        except Exception as e:
            logger.error(f"Error handling error: {str(e)}")

    async def update_orderbooks(self):
        """Оновлення ордербуків для всіх токенів на всіх біржах"""
        self.update_stats['total_updates'] += 1
        current_time = time.time()
        
        logger.info(f"Початок оновлення ордербуків. Всього бірж: {len(self.exchanges)}, токенів: {len(self.tokens)}")
        
        for exchange_name, client in self.exchanges.items():
            logger.info(f"Обробка біржі {exchange_name}")
            
            for token in self.tokens:
                try:
                    # Перевіряємо час останнього оновлення
                    last_update = self.last_update_time.get(token, {}).get(exchange_name, 0)
                    if current_time - last_update < 1:  # Пропускаємо якщо пройшло менше 1 секунди
                        logger.debug(f"Пропускаємо оновлення для {token} на {exchange_name} - занадто швидко")
                        continue
                        
                    logger.info(f"Отримання даних ордербуку для {token} на {exchange_name}")
                    
                    # Отримуємо дані ордербуку
                    orderbook_data = None
                    if exchange_name == "CoinEx":
                        orderbook_data = await self._get_coinex_orderbook(client, token)
                    elif exchange_name == "TradeOgre":
                        orderbook_data = await self._get_tradeogre_orderbook(client, token)
                    elif exchange_name == "Xeggex":
                        # Для Xeggex використовуємо спеціальну обробку
                        orderbook_data = await self._get_xeggex_orderbook(client, token)
                    else:
                        orderbook_data = await self._get_standard_orderbook(client, token)
                        
                    if orderbook_data:
                        best_sell = orderbook_data.get('best_sell')
                        best_buy = orderbook_data.get('best_buy')
                        
                        logger.info(f"Отримано дані для {token} на {exchange_name}: sell={best_sell}, buy={best_buy}")
                        
                        # Перевіряємо чи змінилися ціни
                        current_data = self.orderbooks.get(token, {}).get(exchange_name, {})
                        current_sell = current_data.get('best_sell')
                        current_buy = current_data.get('best_buy')
                        
                        if (best_sell != current_sell or best_buy != current_buy) and self._is_valid_prices(best_sell, best_buy):
                            logger.info(f"Ціни змінилися для {token} на {exchange_name}")
                            logger.info(f"Стара ціна: sell={current_sell}, buy={current_buy}")
                            logger.info(f"Нова ціна: sell={best_sell}, buy={best_buy}")
                            
                            # Оновлюємо кеш
                            self._update_orderbook_cache(exchange_name, token, orderbook_data)
                            
                            # Відправляємо оновлення
                            await self._broadcast_update(exchange_name, token, orderbook_data)
                            
                            self.update_stats['successful_updates'] += 1
                        else:
                            logger.debug(f"Ціни не змінилися для {token} на {exchange_name}")
                    else:
                        logger.warning(f"Не отримано даних ордербуку для {token} на {exchange_name}")
                        self.update_stats['failed_updates'] += 1
                        
                except Exception as e:
                    logger.error(f"Помилка при оновленні ордербуку для {token} на {exchange_name}: {str(e)}")
                    self.update_stats['failed_updates'] += 1
                    self.update_stats['last_error'] = str(e)
                    await self._handle_error(exchange_name, token, e)
                    
        logger.info(f"Завершено оновлення ордербуків. Статистика: {self.update_stats}")
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

    async def _get_xeggex_orderbook(self, client, token: str) -> Dict[str, Any]:
        """
        Отримання даних ордербуку для Xeggex.
        
        Args:
            client: Клієнт Xeggex
            token (str): Символ токена
            
        Returns:
            Dict[str, Any]: Дані ордербуку
        """
        try:
            # Отримуємо дані через асинхронний метод
            orderbook_data = await client.get_orderbook(token)
            if not orderbook_data:
                logger.warning(f"Xeggex: No orderbook data for {token}")
                return None
                
            logger.info(f"Xeggex: Got orderbook data for {token}: {json.dumps(orderbook_data, indent=2)}")
            return orderbook_data
            
        except Exception as e:
            logger.error(f"Error getting Xeggex orderbook for {token}: {str(e)}")
            return None

    async def _remove_client(self, websocket):
        """Видалення відключеного клієнта"""
        if websocket in self.connected_clients:
            self.connected_clients.remove(websocket)
            logger.info(f"Client removed. Total clients: {len(self.connected_clients)}")

    async def add_client(self, websocket):
        """Додавання нового клієнта"""
        self.connected_clients.add(websocket)
        logger.info(f"New client added. Total clients: {len(self.connected_clients)}")

    async def broadcast_update(self, message: Dict[str, Any]):
        """Відправка оновлення всім підключеним клієнтам"""
        for websocket in self.connected_clients:
            try:
                await websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending update to client: {str(e)}")
                await self._remove_client(websocket)
