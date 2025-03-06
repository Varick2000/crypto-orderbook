"""
Базовий клас для підключення до бірж.
"""
import abc
import logging
from typing import Dict, List, Any, Optional, Tuple

# Налаштування логгера
logger = logging.getLogger(__name__)

class BaseExchangeClient(abc.ABC):
    """
    Абстрактний базовий клас для всіх клієнтів бірж.
    Всі конкретні реалізації мають успадковуватися від цього класу.
    """
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        """
        Ініціалізація клієнта біржі.
        
        Args:
            name (str): Назва біржі
            url (str): URL для підключення до API біржі
            config (Dict[str, Any], optional): Додаткова конфігурація
        """
        self.name = name
        self.url = url
        self.config = config or {}
        self.is_connected = False
        
        # Словник ордербуків {token: {'asks': [...], 'bids': [...]}}
        self.orderbooks: Dict[str, Dict[str, List]] = {}
        
        # Список токенів, за якими спостерігаємо
        self.tokens: List[str] = []
        
        logger.info(f"Initialized {self.__class__.__name__} for {name}")
    
    @abc.abstractmethod
    async def connect(self):
        """
        Підключення до біржі.
        """
        pass
    
    @abc.abstractmethod
    async def disconnect(self):
        """
        Відключення від біржі.
        """
        pass
    
    @abc.abstractmethod
    async def subscribe_to_orderbook(self, token: str):
        """
        Підписка на оновлення ордербуку для конкретного токена.
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        pass
    
    @abc.abstractmethod
    async def unsubscribe_from_orderbook(self, token: str):
        """
        Відписка від оновлень ордербуку для конкретного токена.
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        pass
    
    def get_orderbook(self, token: str) -> Dict[str, List]:
        """
        Отримання поточного стану ордербуку для токена.
        
        Args:
            token (str): Символ токена
            
        Returns:
            Dict[str, List]: Словник з asks і bids
        """
        return self.orderbooks.get(token, {'asks': [], 'bids': []})
    
    async def add_token(self, token: str):
        """
        Додавання нового токена для спостереження.
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        if token not in self.tokens:
            self.tokens.append(token)
            self.orderbooks[token] = {'asks': [], 'bids': []}
            
            if self.is_connected:
                await self.subscribe_to_orderbook(token)
                
            logger.info(f"{self.name}: Added token {token}")
    
    async def remove_token(self, token: str):
        """
        Видалення токена зі спостереження.
        
        Args:
            token (str): Символ токена (наприклад, BTC, ETH)
        """
        if token in self.tokens:
            if self.is_connected:
                await self.unsubscribe_from_orderbook(token)
                
            self.tokens.remove(token)
            if token in self.orderbooks:
                del self.orderbooks[token]
                
            logger.info(f"{self.name}: Removed token {token}")
    
    def format_price(self, price: float, volume: float) -> str:
        """
        Форматування ціни та об'єму для виведення.
        
        Args:
            price (float): Ціна
            volume (float): Об'єм
            
        Returns:
            str: Відформатований рядок
        """
        # Форматування ціни залежно від її розміру
        if price < 10:
            formatted_price = f"{price:,.12f}".replace(",", " ")
        elif price < 100:
            formatted_price = f"{price:,.11f}".replace(",", " ")
        else:
            formatted_price = f"{price:,.10f}".replace(",", " ")
        
        # Форматування об'єму
        formatted_volume = f"{volume:.4f}"
        
        return f"{formatted_price} {formatted_volume}"

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
                best_sell = self.format_price(price, volume)
                break
                
        cumulative_volume = 0
        for bid in bids:
            price, volume = float(bid[0]), float(bid[1])
            cumulative_volume += volume * price
            if cumulative_volume >= threshold:
                best_buy = self.format_price(price, volume)
                break
                
        return best_sell or "X X X", best_buy or "X X X"