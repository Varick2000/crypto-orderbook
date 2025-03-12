"""
Клієнт для біржі CoinEx.
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
import websockets
from exchange_clients.base_client import BaseExchangeClient
import aiohttp

logger = logging.getLogger(__name__)

class CoinExClient(BaseExchangeClient):
    """
    Клієнт для біржі CoinEx.
    """
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        super().__init__(name, url, config)
        self.ws = None
        self.is_connected = False
        self.orderbooks = {}
        self.tokens = []
        self.listen_task = None
        self._ws_lock = asyncio.Lock()  # Додаємо блокування для WebSocket операцій
        self.http_client = aiohttp.ClientSession()  # Додаємо HTTP клієнт
        logger.info(f"{self.name}: Ініціалізація клієнта з URL: {self.url}")
        
    async def connect(self):
        """Підключення до WebSocket API біржі"""
        try:
            if self.ws:
                logger.info(f"{self.name}: Закриваємо попереднє з'єднання")
                await self.ws.close()
                
            logger.info(f"{self.name}: Спроба підключення до WebSocket {self.url}")
            self.ws = await websockets.connect(self.url)
            self.is_connected = True
            logger.info(f"{self.name}: WebSocket з'єднання встановлено успішно")
            
            # Запускаємо прослуховування в окремій таcці
            if self.listen_task is None or self.listen_task.done():
                self.listen_task = asyncio.create_task(self.listen())
                logger.info(f"{self.name}: Запущено нову таску прослуховування")
            
            # Підписуємося на ордербуки для всіх токенів
            logger.info(f"{self.name}: Починаємо підписку на токени: {self.tokens}")
            for token in self.tokens:
                symbol = f"{token}USDT"
                try:
                    await self.subscribe(symbol)
                    logger.info(f"{self.name}: Успішно підписались на {symbol}")
                except Exception as e:
                    logger.error(f"{self.name}: Помилка при підписці на {symbol}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"{self.name}: Помилка при підключенні до WebSocket: {str(e)}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        try:
            if self.listen_task and not self.listen_task.done():
                self.listen_task.cancel()
                try:
                    await self.listen_task
                except asyncio.CancelledError:
                    pass
            
            if self.ws:
                await self.ws.close()
            
            self.is_connected = False
            logger.info(f"{self.name}: Відключено від WebSocket")
            return True
        except Exception as e:
            logger.error(f"{self.name}: Помилка при відключенні: {str(e)}")
            return False
    
    async def subscribe(self, symbol: str):
        """Підписка на оновлення ордербуку"""
        try:
            if not self.ws:
                logger.error(f"{self.name}: WebSocket не підключено")
                return
                
            subscription = {
                "method": "depth.subscribe",
                "params": [
                    symbol,
                    50,  # Глибина ордербуку
                    "0", # Точність
                    True # Об'єднувати однакові ціни
                ],
                "id": 1
            }
            
            logger.info(f"{self.name}: Відправка запиту на підписку для {symbol}: {json.dumps(subscription, indent=2, ensure_ascii=False)}")
            async with self._ws_lock:  # Використовуємо блокування для send
                await self.ws.send(json.dumps(subscription))
                
            # Додаємо логування для підтвердження підписки
            confirmation = await self.ws.recv()
            logger.info(f"{self.name}: Отримано підтвердження підписки для {symbol}: {confirmation}")
            
        except Exception as e:
            logger.error(f"{self.name}: Помилка при підписці на {symbol}: {str(e)}")
            # Спробуємо перепідключитися
            if not self.is_connected:
                logger.info(f"{self.name}: Спроба перепідключення після помилки підписки")
                await self.connect()
            raise

    async def listen(self):
        """Прослуховування повідомлень від WebSocket"""
        while True:
            try:
                if not self.is_connected or not self.ws:
                    logger.warning(f"{self.name}: WebSocket не підключено, спроба підключення...")
                    await self.connect()
                    await asyncio.sleep(5)
                    continue

                async with self._ws_lock:
                    message = await self.ws.recv()
                    logger.debug(f"{self.name}: Отримано нове повідомлення: {message[:200]}...")
                    
                data = json.loads(message)
                await self._process_message(data)
                
            except websockets.exceptions.ConnectionClosed as e:
                logger.error(f"{self.name}: WebSocket з'єднання закрито з кодом {e.code}: {e.reason}")
                self.is_connected = False
                # Спробуємо перепідключитися
                try:
                    logger.info(f"{self.name}: Спроба перепідключення після закриття з'єднання")
                    await self.connect()
                except Exception as e:
                    logger.error(f"{self.name}: Помилка при спробі перепідключення: {str(e)}")
                    await asyncio.sleep(5)
            except json.JSONDecodeError as e:
                logger.error(f"{self.name}: Помилка декодування JSON: {str(e)}, повідомлення: {message[:200]}...")
                continue
            except Exception as e:
                logger.error(f"{self.name}: Помилка при обробці повідомлення: {str(e)}")
                await asyncio.sleep(1)
                continue

    async def _process_message(self, message: dict):
        """Обробка повідомлень від WebSocket"""
        try:
            logger.info(f"{self.name}: Отримано повідомлення: {json.dumps(message, indent=2, ensure_ascii=False)}")
            
            # Перевіряємо чи це повідомлення з ордербуком
            if "method" in message:
                if message["method"] == "depth.update":
                    data = message.get("params", [])
                    if len(data) < 2:
                        logger.warning(f"{self.name}: Неправильний формат даних в повідомленні")
                        return
                        
                    # Отримуємо символ з першого параметра
                    symbol = data[0]  # Перший параметр - це символ
                    orderbook = data[1]  # Другий параметр - це дані ордербуку
                    
                    asks = orderbook.get("asks", [])  # [[price, amount], ...]
                    bids = orderbook.get("bids", [])  # [[price, amount], ...]
                    
                    logger.info(f"{self.name}: Отримано оновлення для {symbol}:")
                    logger.info(f"Кількість asks: {len(asks)}, Кількість bids: {len(bids)}")
                    logger.info(f"Приклад asks: {asks[:3]}")
                    logger.info(f"Приклад bids: {bids[:3]}")
                    
                    if asks and bids:
                        try:
                            # Фільтруємо і конвертуємо дані
                            valid_asks = []
                            valid_bids = []
                            
                            for ask in asks:
                                try:
                                    price, amount = ask[0], ask[1]
                                    if float(amount) > 0:
                                        valid_asks.append((price, amount))
                                except (ValueError, IndexError):
                                    continue
                                    
                            for bid in bids:
                                try:
                                    price, amount = bid[0], bid[1]
                                    if float(amount) > 0:
                                        valid_bids.append((price, amount))
                                except (ValueError, IndexError):
                                    continue
                            
                            if valid_asks and valid_bids:
                                # Логуємо вхідні дані
                                logger.info(f"{self.name}: Валідні asks перед обробкою: {valid_asks[:5]}")
                                logger.info(f"{self.name}: Валідні bids перед обробкою: {valid_bids[:5]}")
                                
                                top_ask = min(float(price) for price, _ in valid_asks)
                                top_bid = max(float(price) for price, _ in valid_bids)
                                
                                # Логуємо проміжні значення
                                logger.info(f"{self.name}: Top ask: {top_ask}, Top bid: {top_bid}")
                                
                                # Перетворюємо дані в формат для фронтенду
                                formatted_asks = []
                                formatted_bids = []
                                
                                for price, size in valid_asks:
                                    try:
                                        formatted_asks.append([
                                            str(float(price)),  # Передаємо як рядок
                                            str(float(size))    # Передаємо як рядок
                                        ])
                                    except ValueError as e:
                                        logger.error(f"{self.name}: Помилка конвертації ask: {e}, price={price}, size={size}")
                                        continue
                                    
                                for price, size in valid_bids:
                                    try:
                                        formatted_bids.append([
                                            str(float(price)),  # Передаємо як рядок
                                            str(float(size))    # Передаємо як рядок
                                        ])
                                    except ValueError as e:
                                        logger.error(f"{self.name}: Помилка конвертації bid: {e}, price={price}, size={size}")
                                        continue
                                
                                # Логуємо результат
                                logger.info(f"{self.name}: Форматовані asks: {formatted_asks[:5]}")
                                logger.info(f"{self.name}: Форматовані bids: {formatted_bids[:5]}")
                                
                                # Зберігаємо повний ордербук та найкращі ціни
                                self.orderbooks[symbol] = {
                                    "asks": formatted_asks,
                                    "bids": formatted_bids,
                                    "last_update": message.get("id", 0),
                                    "best_sell": self._format_price(top_ask),
                                    "best_buy": self._format_price(top_bid)
                                }
                            else:
                                self.orderbooks[symbol] = {
                                    "asks": [],
                                    "bids": [],
                                    "last_update": message.get("id", 0),
                                    "best_sell": "X X X",
                                    "best_buy": "X X X"
                                }
                        except Exception as e:
                            logger.error(f"{self.name}: Помилка при обробці даних: {str(e)}")
                            self.orderbooks[symbol] = {
                                "asks": [],
                                "bids": [],
                                "last_update": message.get("id", 0),
                                "best_sell": "X X X",
                                "best_buy": "X X X"
                            }
                    else:
                        self.orderbooks[symbol] = {
                            "asks": [],
                            "bids": [],
                            "last_update": message.get("id", 0),
                            "best_sell": "X X X",
                            "best_buy": "X X X"
                        }
                elif message["method"] == "depth.subscribe":
                    logger.info(f"{self.name}: Підтверджено підписку на ордербук")
                
        except Exception as e:
            logger.error(f"{self.name}: Помилка при обробці повідомлення: {str(e)}")
            logger.error(f"Повідомлення: {message}")
            raise

    async def add_token(self, token: str):
        """Додавання нового токена для відстеження"""
        if token not in self.tokens:
            self.tokens.append(token)
            logger.info(f"{self.name}: Додано токен {token}")
            
            # Отримуємо початковий стан ордербуку
            symbol = f"{token}USDT"
            orderbook = await self.get_orderbook(token)
            if orderbook:
                self.orderbooks[symbol] = orderbook
                logger.info(f"{self.name}: Завантажено початковий ордербук для {symbol}")
            
            # Підключаємося до WebSocket якщо ще не підключені
            if not self.is_connected:
                await self.connect()
                
            if self.is_connected:
                await self.subscribe(symbol)

    async def remove_token(self, token: str):
        """Видалення токена з відстеження"""
        if token in self.tokens:
            self.tokens.remove(token)
            logger.info(f"{self.name}: Видалено токен {token}")

    def get_best_prices(self, symbol: str) -> Dict[str, str]:
        """Отримання найкращих цін для символу"""
        try:
            orderbook = self.orderbooks.get(symbol, {})
            logger.info(f"{self.name}: Отримання цін для {symbol}:")
            logger.info(f"Поточний стан ордербуку: {json.dumps(orderbook, indent=2, ensure_ascii=False)}")
            
            sell = orderbook.get("best_sell", "X X X")
            buy = orderbook.get("best_buy", "X X X")
            
            logger.info(f"{self.name}: Повертаю ціни для {symbol}:")
            logger.info(f"best_sell: {sell}")
            logger.info(f"best_buy: {buy}")
            
            return {
                "best_sell": sell,
                "best_buy": buy
            }
        except Exception as e:
            logger.error(f"{self.name}: Помилка при отриманні цін для {symbol}: {str(e)}")
            return {
                "best_sell": "X X X",
                "best_buy": "X X X"
            }

    def _format_price(self, price: float) -> str:
        """Форматування ціни з відповідною кількістю десяткових знаків."""
        if price >= 1000:
            return f"{price:.2f}"  # Прибираємо пробіли у великих числах
        elif price >= 100:
            return f"{price:.3f}"
        elif price >= 10:
            return f"{price:.4f}"
        elif price >= 1:
            return f"{price:.5f}"
        elif price >= 0.1:
            return f"{price:.6f}"
        elif price >= 0.01:
            return f"{price:.7f}"
        else:
            return f"{price:.8f}"

    async def get_orderbook(self, token: str) -> Dict[str, Any]:
        """Отримання початкового стану ордербуку через REST API"""
        try:
            symbol = f"{token}USDT"
            logger.info(f"{self.name}: Отримання ордербуку для {symbol}")
            
            url = "https://api.coinex.com/v1/market/depth"
            params = {
                "market": symbol,
                "limit": 50,
                "merge": "0"
            }
            
            async with self.http_client.get(url, params=params) as response:
                response_data = await response.json()
                logger.info(f"{self.name}: Отримано відповідь від API: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                
                if response_data.get("code") == 0 and "data" in response_data:
                    data = response_data["data"]
                    asks = data.get("asks", [])  # [[price, amount], ...]
                    bids = data.get("bids", [])  # [[price, amount], ...]
                    
                    if asks and bids:
                        # Конвертуємо ціни в float для порівняння
                        top_ask = min(float(ask[0]) for ask in asks if float(ask[1]) > 0)
                        top_bid = max(float(bid[0]) for bid in bids if float(bid[1]) > 0)
                        
                        # Перетворюємо дані в формат для фронтенду
                        formatted_asks = [[str(float(ask[0])), str(float(ask[1]))] for ask in asks if float(ask[1]) > 0]
                        formatted_bids = [[str(float(bid[0])), str(float(bid[1]))] for bid in bids if float(bid[1]) > 0]
                        
                        logger.info(f"{self.name}: Форматовані дані для {symbol}:")
                        logger.info(f"Приклад asks: {json.dumps(formatted_asks[:5], indent=2)}")
                        logger.info(f"Приклад bids: {json.dumps(formatted_bids[:5], indent=2)}")
                        
                        return {
                            "asks": formatted_asks,
                            "bids": formatted_bids,
                            "last_update": 0,
                            "best_sell": self._format_price(top_ask) if formatted_asks else "X X X",
                            "best_buy": self._format_price(top_bid) if formatted_bids else "X X X"
                        }
                
                logger.warning(f"{self.name}: Не вдалося отримати дані ордербуку для {symbol}")
                return {
                    "asks": [],
                    "bids": [],
                    "last_update": 0,
                    "best_sell": "X X X",
                    "best_buy": "X X X"
                }
                
        except Exception as e:
            logger.error(f"{self.name}: Помилка отримання ордербуку для {symbol}: {str(e)}")
            return {
                "asks": [],
                "bids": [],
                "last_update": 0,
                "best_sell": "X X X",
                "best_buy": "X X X"
            }

    async def _refresh_orderbook(self, token: str):
        """
        Асинхронне оновлення ордербуку для токена.
        
        Args:
            token (str): Символ токена
        """
        try:
            symbol = f"{token}USDT"
            logger.info(f"{self.name}: Асинхронне оновлення ордербуку для {symbol}")
            
            # Запитуємо актуальні дані
            orderbook = await self.get_orderbook(token)
            
            # Оновлюємо кеш, якщо отримали дані
            if orderbook:
                self.orderbooks[symbol] = orderbook
                logger.info(f"{self.name}: Успішно оновлено ордербук для {symbol}")
        except Exception as e:
            logger.error(f"{self.name}: Помилка при оновленні ордербуку для {token}: {str(e)}")

    async def subscribe_to_orderbook(self, token: str):
        """Підписка на оновлення ордербуку для конкретного токена"""
        try:
            symbol = f"{token}USDT"
            await self.subscribe(symbol)
            logger.info(f"{self.name}: Підписано на ордербук для {symbol}")
        except Exception as e:
            logger.error(f"{self.name}: Помилка при підписці на ордербук для {token}: {e}")
            raise

    async def unsubscribe_from_orderbook(self, token: str):
        """Відписка від оновлень ордербуку для конкретного токена"""
        try:
            symbol = f"{token}USDT"
            subscription_key = f"depth.{symbol}"
            if subscription_key in self.subscriptions:
                del self.subscriptions[subscription_key]
                logger.info(f"{self.name}: Відписано від ордербуку для {symbol}")
        except Exception as e:
            logger.error(f"{self.name}: Помилка при відписці від ордербуку для {token}: {e}")
            raise

    async def close(self):
        """Закриття з'єднань"""
        try:
            if self.listen_task and not self.listen_task.done():
                self.listen_task.cancel()
                try:
                    await self.listen_task
                except asyncio.CancelledError:
                    pass
            
            if self.ws:
                await self.ws.close()
            
            if self.http_client:
                await self.http_client.close()
            
            self.is_connected = False
            logger.info(f"{self.name}: Всі з'єднання закрито")
            return True
        except Exception as e:
            logger.error(f"{self.name}: Помилка при закритті з'єднань: {str(e)}")
            return False 