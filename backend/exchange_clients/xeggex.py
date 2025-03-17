import json
import asyncio
import websockets
from .base_client import BaseExchangeClient

class XeggexClient(BaseExchangeClient):
    def __init__(self):
        super().__init__(name="Xeggex", url="wss://ws.xeggex.com/ws/v2")
        self.symbol = "XRG/USDT"  # приклад пари
        self.ws_url = "wss://ws.xeggex.com/ws/v2"  # оновлений URL
        
    async def subscribe_orderbook(self, ws):
        """Підписка на оновлення ордербуку"""
        subscribe_message = {
            "method": "subscribeOrderbook",
            "params": {
                "symbol": self.symbol,
                "limit": 100  # додаємо ліміт для отримання більшої кількості ордерів
            },
            "id": 123
        }
        print(f"Sending subscribe message: {subscribe_message}")  # додаємо логування
        await ws.send(json.dumps(subscribe_message))
        
    async def process_message(self, message):
        """Обробка отриманих повідомлень"""
        try:
            data = json.loads(message)
            print(f"Received message: {data}")  # додаємо логування для діагностики
            
            if "method" in data and data["method"] == "orderbook":
                orderbook_data = data["params"]
                # Форматуємо дані в такий самий формат як у інших клієнтів
                formatted_data = {
                    "bids": [[float(price), float(amount)] for price, amount in orderbook_data["bids"]],
                    "asks": [[float(price), float(amount)] for price, amount in orderbook_data["asks"]]
                }
                return formatted_data
            elif "error" in data:
                print(f"Error from server: {data['error']}")
            return None
        except Exception as e:
            print(f"Error processing message: {e}")
            return None

    async def connect(self):
        """Підключення до WebSocket API та отримання даних"""
        while True:
            try:
                print(f"Attempting to connect to {self.ws_url}")  # додаємо логування
                async with websockets.connect(self.ws_url) as ws:
                    print(f"Connected to {self.ws_url}")  # додаємо логування
                    self.is_connected = True
                    await self.subscribe_orderbook(ws)
                    
                    while True:
                        try:
                            message = await ws.recv()
                            processed_data = await self.process_message(message)
                            if processed_data:
                                self.orderbooks[self.symbol] = processed_data
                        except Exception as e:
                            print(f"Error processing message: {e}")
                            continue
            except Exception as e:
                print(f"WebSocket connection error: {e}")
                self.is_connected = False
                await asyncio.sleep(5)  # Чекаємо перед повторним підключенням
                continue

    async def disconnect(self):
        """Відключення від WebSocket"""
        self.is_connected = False

    async def subscribe_to_orderbook(self, token: str):
        """Підписка на оновлення ордербуку"""
        self.symbol = token
        if self.is_connected:
            # Перепідключаємось для оновлення підписки
            await self.connect()

    async def unsubscribe_from_orderbook(self, token: str):
        """Відписка від оновлень ордербуку"""
        if token == self.symbol:
            await self.disconnect() 