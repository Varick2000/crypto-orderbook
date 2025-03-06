"""
Базовий клас для клієнтів бірж, які використовують WebSocket.
"""
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable

import websockets
from websockets.exceptions import ConnectionClosed

from exchange_clients.base_client import BaseExchangeClient

# Налаштування логгера
logger = logging.getLogger(__name__)


class WebSocketExchangeClient(BaseExchangeClient):
    """
    Базовий клас для клієнтів бірж, які використовують WebSocket API.
    """
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        """
        Ініціалізація WebSocket-клієнта біржі.
        
        Args:
            name (str): Назва біржі
            url (str): URL для WebSocket API
            config (Dict[str, Any], optional): Додаткова конфігурація
        """
        super().__init__(name, url, config)
        self.ws = None
        self.ping_interval = config.get('ping_interval', 30) if config else 30
        self.ping_task = None
        self.listener_task = None
        self.message_handlers = {}
        
    async def connect(self):
        """
        Підключення до WebSocket API біржі.
        """
        try:
            self.ws = await websockets.connect(self.url)
            self.is_connected = True
            logger.info(f"{self.name}: Connected to WebSocket API")
            
            # Запуск задачі для прослуховування повідомлень
            self.listener_task = asyncio.create_task(self._listen_for_messages())
            
            # Запуск задачі для регулярних пінгів (якщо потрібно)
            if hasattr(self, 'ping') and callable(getattr(self, 'ping')):
                self.ping_task = asyncio.create_task(self._ping_periodically())
            
            return True
        except Exception as e:
            logger.error(f"{self.name}: Failed to connect: {str(e)}")
            self.is_connected = False
            return False
            
    async def disconnect(self):
        """
        Відключення від WebSocket API.
        """
        try:
            # Зупинка задач
            if self.listener_task:
                self.listener_task.cancel()
                
            if self.ping_task:
                self.ping_task.cancel()
                
            # Закриття з'єднання
            if self.ws:
                await self.ws.close()
                
            self.is_connected = False
            logger.info(f"{self.name}: Disconnected from WebSocket API")
            return True
        except Exception as e:
            logger.error(f"{self.name}: Error during disconnect: {str(e)}")
            return False
    
    async def _listen_for_messages(self):
        """
        Прослуховування повідомлень від WebSocket API.
        """
        try:
            while True:
                if not self.ws:
                    logger.warning(f"{self.name}: WebSocket connection lost, reconnecting...")
                    await self.connect()
                    await asyncio.sleep(1)
                    continue
                
                try:
                    message = await self.ws.recv()
                    await self._process_message(message)
                except ConnectionClosed:
                    logger.warning(f"{self.name}: WebSocket connection closed, reconnecting...")
                    self.is_connected = False
                    await self.connect()
                except Exception as e:
                    logger.error(f"{self.name}: Error processing message: {str(e)}")
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info(f"{self.name}: Listener task cancelled")
        except Exception as e:
            logger.error(f"{self.name}: Listener task failed: {str(e)}")
    
    async def _ping_periodically(self):
        """
        Відправка періодичних ping-повідомлень для підтримки з'єднання.
        """
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                if self.is_connected and self.ws:
                    await self.ping()
        except asyncio.CancelledError:
            logger.info(f"{self.name}: Ping task cancelled")
        except Exception as e:
            logger.error(f"{self.name}: Ping task failed: {str(e)}")
    
    async def send_message(self, message: Dict[str, Any]):
        """
        Відправка повідомлення через WebSocket.
        
        Args:
            message (Dict[str, Any]): Повідомлення для відправки
        """
        if not self.is_connected or not self.ws:
            logger.warning(f"{self.name}: Cannot send message, not connected")
            return False
            
        try:
            await self.ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"{self.name}: Error sending message: {str(e)}")
            self.is_connected = False
            return False
    
    async def _process_message(self, message: str):
        """
        Обробка отриманого повідомлення від WebSocket.
        
        Args:
            message (str): Отримане повідомлення
        """
        try:
            # Базова реалізація припускає JSON-формат
            data = json.loads(message)
            
            # Перевірка на pong (якщо біржа його відправляє)
            if 'pong' in data or data.get('op') == 'pong':
                return
                
            # Перевірка на помилку
            if 'error' in data or data.get('code', 0) != 0:
                error_msg = data.get('error', str(data))
                logger.error(f"{self.name}: Received error: {error_msg}")
                return
                
            # Спроба визначити тип повідомлення і викликати відповідний обробник
            message_type = self._get_message_type(data)
            
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](data)
            else:
                # Якщо немає відповідного обробника, викликаємо метод для невідомих повідомлень
                await self._handle_unknown_message(data)
                
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: Received non-JSON message: {message[:100]}...")
        except Exception as e:
            logger.error(f"{self.name}: Error processing message: {str(e)}")
    
    def _get_message_type(self, data: Dict[str, Any]) -> str:
        """
        Визначення типу повідомлення. Кожна біржа може мати свій формат.
        
        Args:
            data (Dict[str, Any]): Отримані дані
            
        Returns:
            str: Тип повідомлення
        """
        # Базова реалізація, яку потрібно перевизначити в дочірніх класах
        return data.get('method', data.get('type', data.get('op', 'unknown')))
    
    async def _handle_unknown_message(self, data: Dict[str, Any]):
        """
        Обробка невідомого повідомлення.
        
        Args:
            data (Dict[str, Any]): Отримані дані
        """
        # За замовчуванням просто логуємо повідомлення
        logger.debug(f"{self.name}: Received unknown message type: {str(data)[:100]}...")
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """
        Реєстрація обробника для певного типу повідомлень.
        
        Args:
            message_type (str): Тип повідомлення
            handler (Callable): Функція-обробник
        """
        self.message_handlers[message_type] = handler
    
    # Абстрактні методи, які необхідно реалізувати в дочірніх класах
    
    async def subscribe_to_orderbook(self, token: str):
        """
        Підписка на оновлення ордербуку для конкретного токена.
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        raise NotImplementedError("This method must be implemented in derived classes")
    
    async def unsubscribe_from_orderbook(self, token: str):
        """
        Відписка від оновлень ордербуку для конкретного токена.
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        raise NotImplementedError("This method must be implemented in derived classes")
    
    async def ping(self):
        """
        Відправка ping-повідомлення для підтримки з'єднання.
        """
        raise NotImplementedError("This method must be implemented if ping is required")