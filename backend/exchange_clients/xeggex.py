"""
Клієнт для біржі Xeggex з урахуванням обробки даних у форматі:
- Список словників: [{"price": "...", "quantity": "..."}]
- Список списків: [["price", "quantity"], ...]
і додаткового логування для налагодження.
"""

import asyncio
import json
import logging
import ssl
from typing import Dict, Any, List, Optional

import websockets

from exchange_clients.websocket_client import WebSocketExchangeClient

logger = logging.getLogger(__name__)

class XeggexClient(WebSocketExchangeClient):
    """
    Клієнт для біржі Xeggex.
    Працює через WebSocket, отримує оновлення ордербуку у форматі JSON.
    Підтримує формат списку словників та формат списку списків для asks/bids.
    """

    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        super().__init__(name, url, config)
        # Створення SSL-контексту для безпечного WebSocket-з'єднання
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Основний кеш ордербуків {symbol: {"asks": [...], "bids": [...], "last_update": ...}}
        self.orderbook_cache: Dict[str, Dict[str, Any]] = {}
        self.tokens: List[str] = []

        # Лічильник ping-повідомлень
        self.ping_id = 0

        logger.info(f"{self.name}: Initialized with URL: {url}")

    async def connect(self):
        """
        Підключення до WebSocket API біржі.
        """
        try:
            logger.info(f"{self.name}: Attempting to connect to {self.url}")
            logger.info(f"{self.name}: SSL context: check_hostname={self.ssl_context.check_hostname}, verify_mode={self.ssl_context.verify_mode}")
            
            self.ws = await websockets.connect(self.url, ssl=self.ssl_context)
            self.is_connected = True
            logger.info(f"{self.name}: Successfully connected to WebSocket API")
            logger.info(f"{self.name}: WebSocket object created: {self.ws}")

            # Запуск задачі для прослуховування повідомлень
            self.listener_task = asyncio.create_task(self.listen())
            logger.info(f"{self.name}: Started listener task: {self.listener_task}")

            # Запуск задачі для пінгів
            self.ping_task = asyncio.create_task(self._ping_periodically())
            logger.info(f"{self.name}: Started ping task: {self.ping_task}")

            # Підписуємося на всі токени, якщо вони додані до списку
            logger.info(f"{self.name}: Current tokens list: {self.tokens}")
            for token in self.tokens:
                logger.info(f"{self.name}: Subscribing to {token}")
                await self.subscribe_to_orderbook(token)

            return True
        except Exception as e:
            logger.error(f"{self.name}: Failed to connect: {str(e)}", exc_info=True)
            self.is_connected = False
            return False

    async def disconnect(self):
        """
        Відключення від WebSocket API.
        """
        try:
            if self.listener_task:
                self.listener_task.cancel()
                try:
                    await self.listener_task
                except asyncio.CancelledError:
                    pass
            if self.ping_task:
                self.ping_task.cancel()
                try:
                    await self.ping_task
                except asyncio.CancelledError:
                    pass
            if self.ws:
                await self.ws.close()
                self.ws = None

            self.is_connected = False
            logger.info(f"{self.name}: Disconnected from WebSocket API")
            return True
        except Exception as e:
            logger.error(f"{self.name}: Error during disconnect: {str(e)}")
            return False

    async def subscribe_to_orderbook(self, token: str):
        """
        Підписка на оновлення ордербуку для конкретного токена (наприклад, 'BTC').
        Для Xeggex символ: 'BTC/USDT'.
        """
        if not self.is_connected or not self.ws:
            logger.error(f"{self.name}: WebSocket not connected. Cannot subscribe.")
            return

        symbol = f"{token}/USDT"
        subscribe_message = {
            "jsonrpc": "2.0",
            "method": "subscribeOrderbook",
            "params": {
                "symbol": symbol
            },
            "id": len(self.tokens) + 1
        }

        logger.info(f"{self.name}: Sending subscription message for {symbol}: "
                    f"{json.dumps(subscribe_message, ensure_ascii=False)}")

        # Якщо токен ще не додано в список, додаємо
        if token not in self.tokens:
            self.tokens.append(token)
            logger.info(f"{self.name}: Added token {token}. Current tokens: {self.tokens}")

        try:
            await self.send_message(subscribe_message)
            logger.info(f"{self.name}: Successfully subscribed to {symbol}")
        except Exception as e:
            logger.error(f"{self.name}: Failed to subscribe to {symbol}: {str(e)}")
            if token in self.tokens:
                self.tokens.remove(token)
                logger.info(f"{self.name}: Removed token {token} due to subscription failure")

    async def unsubscribe_from_orderbook(self, token: str):
        """
        Відписка від оновлень ордербуку для конкретного токена (наприклад, 'BTC').
        """
        if not self.is_connected or not self.ws:
            logger.error(f"{self.name}: WebSocket not connected. Cannot unsubscribe.")
            return

        symbol = f"{token}/USDT"
        unsubscribe_message = {
            "jsonrpc": "2.0",
            "method": "unsubscribeOrderbook",
            "params": {
                "symbol": symbol
            },
            "id": 999999  # Умовне число, не критично
        }

        logger.info(f"{self.name}: Sending unsubscribe message for {symbol}: "
                    f"{json.dumps(unsubscribe_message, ensure_ascii=False)}")

        try:
            await self.send_message(unsubscribe_message)
            logger.info(f"{self.name}: Successfully unsubscribed from {symbol}")
        except Exception as e:
            logger.error(f"{self.name}: Failed to unsubscribe from {symbol}: {str(e)}")

    async def _ping_periodically(self):
        """
        Періодична відправка ping-повідомлень для підтримки з'єднання.
        """
        ping_interval = self.config.get('ping_interval', 30)
        logger.info(f"{self.name}: Starting periodic ping with interval {ping_interval} seconds")

        try:
            while self.is_connected:
                await asyncio.sleep(ping_interval)
                if not self.is_connected:
                    break
                await self.ping()
        except asyncio.CancelledError:
            logger.info(f"{self.name}: Ping loop cancelled")
        except Exception as e:
            logger.error(f"{self.name}: Error in ping loop: {str(e)}")
            self.is_connected = False

    async def ping(self):
        """
        Відправка ping-повідомлення (для збереження WebSocket-з'єднання).
        """
        try:
            self.ping_id += 1
            ping_message = {
                "jsonrpc": "2.0",
                "method": "ping",
                "params": {},
                "id": self.ping_id
            }
            logger.debug(f"{self.name}: Sending ping message: {json.dumps(ping_message)}")
            success = await self.send_message(ping_message)
            if not success:
                logger.warning(f"{self.name}: Failed to send ping message")
        except Exception as e:
            logger.error(f"{self.name}: Error sending ping: {str(e)}")
            self.is_connected = False

    async def _process_message(self, message: str):
        """
        Обробка вхідних WebSocket повідомлень.
        Враховує формати:
          - Список словників: [{"price": "...", "quantity": "..."}]
          - Список списків: [["price", "quantity"], ...]
        """
        try:
            data = json.loads(message)
            logger.info(f"{self.name}: Отримано повідомлення: {json.dumps(data, indent=2)}")

            if "method" in data:
                method = data["method"]
                logger.info(f"{self.name}: Метод повідомлення: {method}")

                if method == "snapshotOrderbook":
                    params = data.get('params', {})
                    symbol = params.get('symbol', '').replace('/USDT', '')
                    logger.info(f"{self.name}: Отримано снапшот для {symbol}")

                    if not symbol:
                        logger.error(f"{self.name}: Відсутній символ в снапшоті")
                        return

                    asks = params.get('asks', [])
                    bids = params.get('bids', [])
                    logger.info(f"{self.name}: Кількість asks: {len(asks)}, bids: {len(bids)}")

                    # Якщо дані для asks/bids приходять у вигляді список списків
                    # конвертуємо у словники з ключами "price", "quantity"
                    if asks and isinstance(asks[0], list):
                        logger.info(f"{self.name}: Конвертуємо asks для {symbol} з list[list] у list[dict]")
                        # Конвертуємо дані у словник формат
                        asks = [{"price": str(ask[0]), "amount": str(ask[1])} for ask in asks]
                        logger.info(f"{self.name}: Приклад ask після конвертації: {json.dumps(asks[0], indent=2)}")
                        logger.info(f"{self.name}: Перші 3 asks після конвертації: {json.dumps(asks[:3], indent=2)}")

                    if bids and isinstance(bids[0], list):
                        logger.info(f"{self.name}: Конвертуємо bids для {symbol} з list[list] у list[dict]")
                        # Конвертуємо дані у словник формат
                        bids = [{"price": str(bid[0]), "amount": str(bid[1])} for bid in bids]
                        logger.info(f"{self.name}: Приклад bid після конвертації: {json.dumps(bids[0], indent=2)}")
                        logger.info(f"{self.name}: Перші 3 bids після конвертації: {json.dumps(bids[:3], indent=2)}")

                    # Оновлюємо кеш
                    self.orderbook_cache[symbol] = {
                        'asks': asks,
                        'bids': bids,
                        'last_update': asyncio.get_event_loop().time()
                    }
                    logger.info(f"{self.name}: Оновлено кеш ордербуку для {symbol}")
                    logger.info(f"{self.name}: Поточний стан кешу: {json.dumps(self.orderbook_cache.get(symbol, {}), indent=2)}")

                elif method == "orderbookUpdate":
                    params = data.get('params', {})
                    symbol = params.get('symbol', '').replace('/USDT', '')

                    if not symbol or symbol not in self.orderbook_cache:
                        logger.error(f"{self.name}: Невідомий або відсутній символ в оновленні: {symbol}")
                        return

                    asks = params.get('asks', [])
                    bids = params.get('bids', [])

                    if asks and isinstance(asks[0], list):
                        logger.info(f"{self.name}: Конвертуємо оновлення asks для {symbol} з list[list] у list[dict]")
                        # Конвертуємо дані у словник формат
                        asks = [{"price": str(ask[0]), "amount": str(ask[1])} for ask in asks]
                    if bids and isinstance(bids[0], list):
                        logger.info(f"{self.name}: Конвертуємо оновлення bids для {symbol} з list[list] у list[dict]")
                        # Конвертуємо дані у словник формат
                        bids = [{"price": str(bid[0]), "amount": str(bid[1])} for bid in bids]

                    # Логуємо конвертовані дані для оновлення
                    logger.info(f"{self.name}: Конвертовані дані оновлення - asks={json.dumps(asks[:3], indent=2)}, bids={json.dumps(bids[:3], indent=2)}")

                    # Застосовуємо оновлення
                    if asks:
                        self.orderbook_cache[symbol]['asks'] = asks
                    if bids:
                        self.orderbook_cache[symbol]['bids'] = bids

                    self.orderbook_cache[symbol]['last_update'] = asyncio.get_event_loop().time()
                    logger.info(f"{self.name}: Оновлено ордербук для {symbol}")
                    logger.info(f"{self.name}: Поточний стан кешу після оновлення: {json.dumps(self.orderbook_cache.get(symbol, {}), indent=2)}")

            elif "result" in data:
                # Це відповіді на запити (наприклад, ping/pong)
                logger.info(f"{self.name}: Обробка результату повідомлення")
                # Можна додати обробку "pong" тощо
                pass
            else:
                logger.info(f"{self.name}: Повідомлення не містить 'method' чи 'result' поля. Пропускаємо.")

        except json.JSONDecodeError:
            logger.warning(f"{self.name}: Отримано не-JSON повідомлення: {message[:100]}...")
        except Exception as e:
            logger.error(f"{self.name}: Помилка при обробці повідомлення: {str(e)}")
            logger.error(f"{self.name}: Повідомлення: {message}")

    async def get_orderbook(self, token: str) -> Dict[str, Any]:
        """
        Отримання даних ордербуку для токена.
        
        Args:
            token (str): Символ токена
            
        Returns:
            Dict[str, Any]: Дані ордербуку
        """
        try:
            # Отримуємо дані з кешу WebSocket
            orderbook = self.orderbook_cache.get(token)
            if not orderbook:
                logger.warning(f"Xeggex: No orderbook data for {token}")
                return None
                
            # Отримуємо asks та bids
            asks = orderbook.get('asks', [])
            bids = orderbook.get('bids', [])
            
            if not asks or not bids:
                logger.warning(f"Xeggex: Empty orderbook for {token}")
                return None
                
            # Отримуємо найкращі ціни
            best_sell = asks[0]['price'] if asks else None
            best_buy = bids[0]['price'] if bids else None
            
            if not best_sell or not best_buy:
                logger.warning(f"Xeggex: Missing best prices for {token}")
                return None
                
            logger.info(f"Xeggex: Got orderbook data for {token}: sell={best_sell}, buy={best_buy}")
            return {
                'asks': asks,
                'bids': bids,
                'best_sell': best_sell,
                'best_buy': best_buy
            }
            
        except Exception as e:
            logger.error(f"Error getting Xeggex orderbook for {token}: {str(e)}")
            return None

    def get_best_prices(self, token: str) -> Dict[str, str]:
        """
        Отримання найкращих цін (best_sell, best_buy) для заданого токена.
        """
        try:
            ob = self.get_orderbook(token)
            asks = ob.get('asks', [])
            bids = ob.get('bids', [])

            if not asks or not bids:
                logger.warning(f"{self.name}: Empty orderbook for {token}")
                return {'best_sell': 'X X X', 'best_buy': 'X X X'}

            # Припускаємо, що asks відсортовані за зростанням ціни, а bids - за спаданням.
            best_sell_str = asks[0]['price']
            best_buy_str = bids[0]['price']

            logger.info(f"{self.name}: Best prices for {token}: sell={best_sell_str}, buy={best_buy_str}")
            return {'best_sell': best_sell_str, 'best_buy': best_buy_str}

        except Exception as e:
            logger.error(f"{self.name}: Error getting best prices for {token}: {str(e)}")
            return {'best_sell': 'X X X', 'best_buy': 'X X X'}

    async def send_message(self, message: Dict[str, Any]):
        """
        Відправка повідомлення через WebSocket.
        
        Args:
            message (Dict[str, Any]): Повідомлення для відправки
        """
        if not self.is_connected or not self.ws:
            logger.warning(f"{self.name}: Cannot send message, not connected. Connected status: {self.is_connected}, WebSocket: {self.ws}")
            return False
            
        try:
            message_str = json.dumps(message)
            logger.info(f"{self.name}: Sending message: {message_str}")
            await self.ws.send(message_str)
            logger.info(f"{self.name}: Message sent successfully")
            return True
        except websockets.exceptions.ConnectionClosed as cc:
            logger.warning(f"{self.name}: Connection closed while sending message (code: {cc.code}, reason: {cc.reason})")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"{self.name}: Error sending message: {str(e)}", exc_info=True)
            self.is_connected = False
            return False

    async def _listen_for_messages(self):
        """
        Прослуховування повідомлень від WebSocket API.
        """
        logger.info(f"{self.name}: Starting message listener")
        try:
            while True:
                if not self.ws:
                    logger.warning(f"{self.name}: WebSocket connection lost, reconnecting...")
                    await self.connect()
                    await asyncio.sleep(1)
                    continue
                
                try:
                    logger.debug(f"{self.name}: Waiting for message...")
                    message = await self.ws.recv()
                    logger.info(f"{self.name}: Received raw message: {message[:200]}...")
                    await self._process_message(message)
                except websockets.exceptions.ConnectionClosed as cc:
                    logger.warning(f"{self.name}: WebSocket connection closed (code: {cc.code}, reason: {cc.reason}), reconnecting...")
                    self.is_connected = False
                    await self.connect()
                except Exception as e:
                    logger.error(f"{self.name}: Error processing message: {str(e)}", exc_info=True)
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info(f"{self.name}: Listener task cancelled")
        except Exception as e:
            logger.error(f"{self.name}: Listener task failed: {str(e)}", exc_info=True)

    async def listen(self):
        """
        Публічний метод для запуску прослуховування повідомлень.
        """
        logger.info(f"{self.name}: Starting listener")
        try:
            while True:
                if not self.ws:
                    logger.warning(f"{self.name}: WebSocket connection lost, reconnecting...")
                    await self.connect()
                    await asyncio.sleep(1)
                    continue
                
                try:
                    logger.debug(f"{self.name}: Waiting for message...")
                    message = await self.ws.recv()
                    logger.info(f"{self.name}: Received raw message: {message[:200]}...")
                    await self._process_message(message)
                except websockets.exceptions.ConnectionClosed as cc:
                    logger.warning(f"{self.name}: WebSocket connection closed (code: {cc.code}, reason: {cc.reason}), reconnecting...")
                    self.is_connected = False
                    await self.connect()
                except Exception as e:
                    logger.error(f"{self.name}: Error processing message: {str(e)}", exc_info=True)
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info(f"{self.name}: Listener task cancelled")
        except Exception as e:
            logger.error(f"{self.name}: Listener task failed: {str(e)}", exc_info=True)

    async def add_token(self, token: str):
        """
        Додавання токена до списку для підписки.
        
        Args:
            token (str): Символ токена
        """
        if token not in self.tokens:
            self.tokens.append(token)
            logger.info(f"{self.name}: Added token {token}. Current tokens: {self.tokens}")
            
            # Якщо клієнт вже підключений, підписуємося на оновлення
            if self.is_connected:
                await self.subscribe_to_orderbook(token)
        else:
            logger.debug(f"{self.name}: Token {token} already exists in the list")

    async def remove_token(self, token: str):
        """
        Видалення токена зі списку та відписка від оновлень.
        
        Args:
            token (str): Символ токена
        """
        if token in self.tokens:
            self.tokens.remove(token)
            logger.info(f"{self.name}: Removed token {token}. Current tokens: {self.tokens}")
            
            # Якщо клієнт підключений, відписуємося від оновлень
            if self.is_connected:
                await self.unsubscribe_from_orderbook(token)
                
            # Видаляємо дані з кешу
            if token in self.orderbook_cache:
                del self.orderbook_cache[token]
                logger.info(f"{self.name}: Removed orderbook cache for {token}")
        else:
            logger.debug(f"{self.name}: Token {token} not found in the list")
