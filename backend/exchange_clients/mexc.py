"""
Клієнт для біржі MEXC.
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
import websockets
import aiohttp
from datetime import datetime
from exchange_clients.base_client import BaseExchangeClient

logger = logging.getLogger(__name__)

class MEXCClient(BaseExchangeClient):
    """
    Клієнт для біржі MEXC.
    """
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        """
        Ініціалізація клієнта MEXC.
        
        Args:
            name (str): Назва біржі
            url (str): URL для WebSocket API
            config (Dict[str, Any], optional): Додаткова конфігурація
        """
        super().__init__(name, url, config)
        self.ws = None
        self.ping_task = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.get('max_reconnect_attempts', 3)
        self.reconnect_interval = config.get('reconnect_interval', 5)
        self.ping_interval = config.get('ping_interval', 30)
        self.subscriptions: Dict[str, List[str]] = {}
        self.callbacks = {}
        self.orderbooks = {}
        self.tokens = []
        self.is_connected = False
        self.http_client = aiohttp.ClientSession()
        
    async def connect(self):
        """
        Підключення до WebSocket API MEXC.
        """
        try:
            self.ws = await websockets.connect(self.url)
            self.is_connected = True
            self.reconnect_attempts = 0
            
            # Запуск пінга
            self.ping_task = asyncio.create_task(self._ping())
            
            # Запуск прослуховування повідомлень
            self.listen_task = asyncio.create_task(self.listen())
            
            logger.info(f"{self.name}: Connected to WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to connect to WebSocket: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """
        Відключення від WebSocket API MEXC.
        """
        try:
            if self.ping_task:
                self.ping_task.cancel()
                
            if hasattr(self, 'listen_task'):
                self.listen_task.cancel()
                
            if self.ws:
                await self.ws.close()
                
            if self.http_client:
                await self.http_client.close()
                
            self.is_connected = False
            logger.info(f"{self.name}: Disconnected from WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"{self.name}: Error during disconnect: {str(e)}")
            return False
    
    async def subscribe(self, symbol: str, channel: str, callback):
        """Підписка на канал даних."""
        if not self.ws:
            await self.connect()
        
        subscription_key = f"{symbol}_{channel}"
        if subscription_key not in self.callbacks:
            self.callbacks[subscription_key] = []
        
        self.callbacks[subscription_key].append(callback)
        
        # Використовуємо шаблон підписки з конфігурації
        subscribe_template = self.config.get("subscribe_template", {
            "method": "SUBSCRIPTION",
            "params": ["spot@public.limit.depth.v3.api@$TOKEN_USDT@5"]
        })
        
        # Підставляємо символ в шаблон
        params = [param.replace("$TOKEN", symbol) for param in subscribe_template["params"]]
        
        subscribe_message = {
            "method": subscribe_template["method"],
            "params": params,
            "id": len(self.subscriptions) + 1
        }
        
        try:
            await self.ws.send(json.dumps(subscribe_message))
            logger.info(f"{self.name}: Підписка на {subscription_key} успішна")
        except Exception as e:
            logger.error(f"{self.name}: Помилка при підписці на {subscription_key}: {e}")

    async def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        """Отримання ордербука для вказаного символу"""
        try:
            logger.info(f"Getting orderbook for {symbol} on MEXC")
            url = f"https://api.mexc.com/api/v3/depth"
            params = {"symbol": symbol, "limit": 100}
            async with self.http_client.get(url, params=params) as response:
                response_data = await response.json()
                if response_data and 'bids' in response_data and 'asks' in response_data:
                    best_buy = float(response_data['bids'][0][0]) if response_data['bids'] else 'X X X'
                    best_sell = float(response_data['asks'][0][0]) if response_data['asks'] else 'X X X'
                    logger.info(f"Received orderbook data for {symbol}: sell={best_sell}, buy={best_buy}")
                    return {
                        'best_sell': best_sell,
                        'best_buy': best_buy,
                        'asks': response_data['asks'],
                        'bids': response_data['bids']
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting orderbook for {symbol} on MEXC: {str(e)}")
            return None

    async def get_ticker(self, symbol: str) -> Dict:
        """Отримання поточної ціни та об'єму через REST API."""
        async with self.http_client.get(f"https://api.mexc.com/api/v3/ticker/24hr", params={"symbol": symbol}) as response:
            return await response.json()

    async def listen(self):
        """Прослуховування повідомлень від WebSocket."""
        while self.is_connected:
            try:
                message = await self.ws.recv()
                await self._process_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"{self.name}: WebSocket з'єднання закрито, перепідключення...")
                await self._handle_reconnect()
            except Exception as e:
                logger.error(f"{self.name}: Помилка при обробці повідомлення: {e}")
                await asyncio.sleep(1)  # Чекаємо перед повторною спробою

    async def _process_message(self, message: str):
        """Обробка отриманого повідомлення."""
        try:
            data = json.loads(message)
            
            # Перевіряємо, чи це відповідь на підписку
            if "id" in data and "result" in data:
                logger.info(f"{self.name}: Підписка підтверджена: {data}")
                return
            
            # Перевіряємо, чи це оновлення даних
            if "channel" in data:
                channel = data["channel"]
                symbol = data["symbol"]
                subscription_key = f"{symbol}_{channel}"
                
                if subscription_key in self.callbacks:
                    for callback in self.callbacks[subscription_key]:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(f"{self.name}: Помилка при виклику callback для {subscription_key}: {e}")
                        
                # Обробка даних ордербука
                if channel == "public.limit.depth.v3.api":
                    await self._handle_depth_update(data)
            
        except json.JSONDecodeError:
            logger.error(f"{self.name}: Помилка декодування JSON: {message}")
        except Exception as e:
            logger.error(f"{self.name}: Помилка при обробці повідомлення: {e}")
            logger.error(f"{self.name}: Повідомлення: {message}")

    async def _handle_depth_update(self, data: Dict[str, Any]):
        """Обробка оновлення даних ордербука."""
        try:
            logger.info(f"{self.name}: Отримано оновлення даних: {data}")
            
            if "symbol" not in data:
                logger.error(f"{self.name}: Відсутній символ в даних: {data}")
                return
                
            symbol = data["symbol"]
            if symbol not in self.orderbooks:
                self.orderbooks[symbol] = {
                    "asks": [],
                    "bids": [],
                    "last_update": 0
                }
                logger.info(f"{self.name}: Створено новий ордербук для {symbol}")
            
            # Оновлюємо дані ордербука
            asks = data.get("asks", [])
            bids = data.get("bids", [])
            
            if not asks and not bids:
                logger.warning(f"{self.name}: Отримано пусті дані для {symbol}")
                return
                
            self.orderbooks[symbol]["asks"] = sorted(asks, key=lambda x: float(x[0]))
            self.orderbooks[symbol]["bids"] = sorted(bids, key=lambda x: float(x[0]), reverse=True)
            self.orderbooks[symbol]["last_update"] = data.get("lastUpdateId", 0)
            
            logger.info(f"{self.name}: Оновлено ордербук для {symbol}")
            logger.info(f"{self.name}: Кількість asks: {len(asks)}, bids: {len(bids)}")
            if asks:
                logger.info(f"{self.name}: Найкраща ціна продажу: {asks[0]}")
            if bids:
                logger.info(f"{self.name}: Найкраща ціна купівлі: {bids[0]}")
            
        except Exception as e:
            logger.error(f"{self.name}: Помилка при обробці оновлення ордербука: {e}")
            logger.error(f"{self.name}: Дані, що викликали помилку: {data}")

    async def _ping(self):
        """
        Відправка пінга для підтримки з'єднання.
        """
        while self.is_connected:
            try:
                await self.ws.send(json.dumps({"method": "PING"}))
                await asyncio.sleep(self.ping_interval)
            except Exception as e:
                logger.error(f"{self.name}: Error sending ping: {str(e)}")
                break
    
    async def _handle_reconnect(self):
        """
        Обробка перепідключення при втраті з'єднання.
        """
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            logger.info(f"{self.name}: Attempting to reconnect ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
            
            await asyncio.sleep(self.reconnect_interval)
            await self.connect()
        else:
            logger.error(f"{self.name}: Max reconnection attempts reached")
            self.is_connected = False

    async def add_token(self, token: str):
        """Додавання токена для спостереження."""
        if token not in self.tokens:
            self.tokens.append(token)
            logger.info(f"{self.name}: Added token {token}")
            
            # Підписуємося на оновлення для нового токена
            if self.is_connected:
                await self.subscribe(token, "public.limit.depth.v3.api", self._handle_depth_update)
                
            # Отримуємо початковий стан ордербука
            symbol = f"{token}USDT"
            orderbook = await self.get_orderbook(symbol)
            if orderbook:
                self.orderbooks[symbol] = {
                    "asks": orderbook.get("asks", []),
                    "bids": orderbook.get("bids", []),
                    "last_update": 0
                }
                logger.info(f"{self.name}: Initial orderbook loaded for {symbol}")

    async def remove_token(self, token: str):
        """Видалення токена зі списку спостереження."""
        if token in self.tokens:
            self.tokens.remove(token)
            logger.info(f"{self.name}: Removed token {token}")
            
    def get_best_prices(self, token: str, threshold: float = 5.0) -> Tuple[str, str]:
        """Отримання найкращих цін для токена."""
        symbol = f"{token}USDT"
        if symbol not in self.orderbooks:
            return "X X X", "X X X"
            
        orderbook = self.orderbooks[symbol]
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
                # Форматування ціни залежно від її розміру
                if price < 10:
                    formatted_price = f"{price:,.12f}".replace(",", " ")
                elif price < 100:
                    formatted_price = f"{price:,.11f}".replace(",", " ")
                else:
                    formatted_price = f"{price:,.10f}".replace(",", " ")
                
                best_sell = formatted_price
                break
                
        cumulative_volume = 0
        for bid in bids:
            price, volume = float(bid[0]), float(bid[1])
            cumulative_volume += volume * price
            if cumulative_volume >= threshold:
                # Форматування ціни залежно від її розміру
                if price < 10:
                    formatted_price = f"{price:,.12f}".replace(",", " ")
                elif price < 100:
                    formatted_price = f"{price:,.11f}".replace(",", " ")
                else:
                    formatted_price = f"{price:,.10f}".replace(",", " ")
                
                best_buy = formatted_price
                break
                
        return best_sell or "X X X", best_buy or "X X X"

    async def subscribe_to_orderbook(self, token: str):
        """Підписка на оновлення ордербуку для конкретного токена."""
        if self.is_connected:
            await self.subscribe(token, "public.limit.depth.v3.api", self._handle_depth_update)
            logger.info(f"{self.name}: Subscribed to orderbook for {token}")

    async def unsubscribe_from_orderbook(self, token: str):
        """Відписка від оновлень ордербуку для конкретного токена."""
        if self.is_connected and self.ws:
            symbol = f"{token}USDT"
            unsubscribe_message = {
                "method": "UNSUBSCRIBE",
                "params": [f"spot@public.limit.depth.v3.api@{symbol}@5"],
                "id": len(self.subscriptions) + 1
            }
            await self.ws.send(json.dumps(unsubscribe_message))
            logger.info(f"{self.name}: Unsubscribed from orderbook for {token}")

    async def close(self):
        """Закриття з'єднання."""
        return await self.disconnect()