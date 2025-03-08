"""
Базовий клас для клієнтів бірж, які використовують HTTP API замість WebSocket.
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Tuple

import httpx

from exchange_clients.base_client import BaseExchangeClient
from config import POLLING_INTERVAL

# Налаштування логгера
logger = logging.getLogger(__name__)


class HttpExchangeClient(BaseExchangeClient):
    """
    Базовий клас для клієнтів бірж, які використовують HTTP API.
    """
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        """
        Ініціалізація HTTP-клієнта біржі.
        
        Args:
            name (str): Назва біржі
            url (str): Базовий URL для HTTP API
            config (Dict[str, Any], optional): Додаткова конфігурація
        """
        super().__init__(name, url, config)
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.polling_interval = config.get('polling_interval', POLLING_INTERVAL) if config else POLLING_INTERVAL
        self.polling_tasks = {}  # {token: task}
        self.last_update_time = {}  # {token: timestamp}
    
    async def connect(self):
        """
        Підключення до HTTP API біржі (запуск polling задач).
        """
        try:
            self.is_connected = True
            logger.info(f"{self.name}: HTTP client initialized")
            
            # Запуск задач для polling всіх токенів
            for token in self.tokens:
                await self.subscribe_to_orderbook(token)
                
            return True
        except Exception as e:
            logger.error(f"{self.name}: Failed to initialize HTTP client: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """
        Відключення від HTTP API (зупинка polling задач).
        """
        try:
            # Зупинка всіх задач polling
            for token, task in self.polling_tasks.items():
                if not task.done():
                    task.cancel()
                    
            self.polling_tasks = {}
            
            # Закриття HTTP клієнта
            await self.http_client.aclose()
            
            self.is_connected = False
            logger.info(f"{self.name}: HTTP client closed")
            return True
        except Exception as e:
            logger.error(f"{self.name}: Error during HTTP client shutdown: {str(e)}")
            return False
    
    async def subscribe_to_orderbook(self, token: str):
        """
        Підписка на оновлення ордербуку для конкретного токена (запуск polling задачі).
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        if token in self.polling_tasks:
            # Якщо задача вже існує, але завершена - створюємо нову
            if self.polling_tasks[token].done():
                self.polling_tasks[token] = asyncio.create_task(self._poll_orderbook(token))
        else:
            # Створюємо нову задачу
            self.polling_tasks[token] = asyncio.create_task(self._poll_orderbook(token))
            
        logger.info(f"{self.name}: Started polling for {token}")
    
    async def unsubscribe_from_orderbook(self, token: str):
        """
        Відписка від оновлень ордербуку для конкретного токена (зупинка polling задачі).
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        if token in self.polling_tasks:
            task = self.polling_tasks[token]
            if not task.done():
                task.cancel()
                
            del self.polling_tasks[token]
            
            if token in self.last_update_time:
                del self.last_update_time[token]
                
            logger.info(f"{self.name}: Stopped polling for {token}")
    
    async def _poll_orderbook(self, token: str):
        """
        Періодичне опитування API для оновлення ордербуку.
        
        Args:
            token (str): Символ токена
        """
        try:
            while self.is_connected:
                try:
                    # Отримання і обробка даних ордербуку
                    orderbook = await self.get_orderbook(token)
                    if orderbook:
                        self.orderbooks[token] = orderbook
                        self.last_update_time[token] = time.time()
                        logger.info(f"{self.name}: Updated orderbook for {token}")
                    else:
                        logger.warning(f"{self.name}: No orderbook data received for {token}")
                        
                except Exception as e:
                    logger.error(f"{self.name}: Error polling orderbook for {token}: {str(e)}")
                    # Очищення ордербуку при помилці
                    if token in self.orderbooks:
                        self.orderbooks[token] = {'asks': [], 'bids': [], 'best_sell': 'X X X', 'best_buy': 'X X X'}
                
                # Очікування перед наступним запитом
                await asyncio.sleep(self.polling_interval)
                
        except asyncio.CancelledError:
            logger.info(f"{self.name}: Polling task for {token} cancelled")
        except Exception as e:
            logger.error(f"{self.name}: Polling task for {token} failed: {str(e)}")
    
    def get_endpoint_url(self, token: str) -> str:
        """
        Побудова URL-адреси для запиту ордербуку.
        За замовчуванням використовує шаблон з конфігурації.
        
        Args:
            token (str): Символ токена
            
        Returns:
            str: URL для запиту
        """
        # Використання шаблону з конфігурації
        endpoint_template = self.config.get('endpoint_template', '$URL/$TOKEN-USDT')
        
        # Заміна параметрів у шаблоні
        endpoint = endpoint_template.replace('$URL', self.url).replace('$TOKEN', token)
        
        return endpoint
    
    async def _fetch_and_process_orderbook(self, token: str):
        """
        Отримання та обробка даних ордербуку для токена.
        За замовчуванням створює порожній ордербук.
        
        Args:
            token (str): Символ токена
        """
        self.orderbooks[token] = {'asks': [], 'bids': []}
        logger.error(f"{self.name}: The method _fetch_and_process_orderbook must be implemented in derived classes")

    async def get_orderbook(self, token: str) -> Dict[str, List]:
        """
        Отримання поточного стану ордербуку для токена.
        
        Args:
            token (str): Символ токена
            
        Returns:
            Dict[str, List]: Словник з asks і bids
        """
        return self.orderbooks.get(token, {'asks': [], 'bids': []})

    def get_best_prices(self, token: str, threshold: float = 5.0) -> Tuple[str, str]:
        """
        Отримання найкращих цін для токена з урахуванням кумулятивного обсягу.
        
        Args:
            token (str): Символ токена
            threshold (float): Поріг кумулятивного обсягу
            
        Returns:
            Tuple[str, str]: (best_sell, best_buy)
        """
        if token not in self.orderbooks:
            return "X X X", "X X X"
            
        orderbook = self.orderbooks[token]
        asks = orderbook.get('asks', [])
        bids = orderbook.get('bids', [])
        
        if not asks or not bids:
            return "X X X", "X X X"
            
        # Розрахунок кумулятивного обсягу
        cumulative_volume = 0
        best_sell = None
        best_buy = None
        
        for ask in asks:
            price, volume = float(ask[0]), float(ask[1])
            cumulative_volume += volume * price
            if cumulative_volume >= threshold:
                best_sell = f"{price:.8f}"
                break
                
        cumulative_volume = 0
        for bid in bids:
            price, volume = float(bid[0]), float(bid[1])
            cumulative_volume += volume * price
            if cumulative_volume >= threshold:
                best_buy = f"{price:.8f}"
                break
                
        return best_sell or "X X X", best_buy or "X X X"