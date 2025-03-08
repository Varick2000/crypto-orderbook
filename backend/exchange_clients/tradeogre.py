"""
Клієнт для біржі TradeOgre.
"""
import json
import logging
from typing import Dict, List, Any, Tuple

from exchange_clients.http_client import HttpExchangeClient

# Налаштування логгера
logger = logging.getLogger(__name__)


class TradeOgreClient(HttpExchangeClient):
    """
    Клієнт для біржі TradeOgre.
    """
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        """
        Ініціалізація клієнта TradeOgre.
        
        Args:
            name (str): Назва біржі
            url (str): URL для HTTP API
            config (Dict[str, Any], optional): Додаткова конфігурація
        """
        super().__init__(name, url, config)
    
    def get_endpoint_url(self, token: str) -> str:
        """
        Побудова URL-адреси для запиту ордербуку.
        
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
        
        Args:
            token (str): Символ токена
        """
        endpoint = self.get_endpoint_url(token)
        
        try:
            # Виконання HTTP-запиту
            response = await self.http_client.get(endpoint)
            response.raise_for_status()
            
            # Розбір JSON-відповіді
            data = response.json()
            
            # Перевірка на успішну відповідь
            if 'success' in data and not data['success']:
                logger.error(f"{self.name}: API error: {data.get('error', 'Unknown error')}")
                return
                
            # Отримання даних ордербуку
            # Для sell ордерів беремо тільки ті, що мають ненульову кількість
            asks = [[float(price), float(amount)] for price, amount in data.get('sell', {}).items() if float(amount) > 0]
            # Для buy ордерів беремо тільки ті, що мають ненульову кількість
            bids = [[float(price), float(amount)] for price, amount in data.get('buy', {}).items() if float(amount) > 0]
            
            # Сортування ордерів
            asks.sort(key=lambda x: x[0])  # Сортування за зростанням ціни
            bids.sort(key=lambda x: x[0], reverse=True)  # Сортування за спаданням ціни
            
            # Оновлення локального ордербуку
            self.orderbooks[token] = {
                'asks': asks,
                'bids': bids
            }
            
            # Отримання найкращих цін
            best_buy = None
            best_sell = None
            
            if bids:
                best_buy = bids[0][0]  # Перший ордер з відсортованих bids
            if asks:
                best_sell = asks[0][0]  # Перший ордер з відсортованих asks
                
            logger.debug(f"{self.name}: Updated orderbook for {token}, asks: {len(asks)}, bids: {len(bids)}")
            logger.debug(f"{self.name}: Best prices for {token}: sell={best_sell}, buy={best_buy}")
            if asks:
                logger.debug(f"{self.name}: Sample asks for {token}: {asks[:3]}")
            if bids:
                logger.debug(f"{self.name}: Sample bids for {token}: {bids[:3]}")
            
        except Exception as e:
            logger.error(f"{self.name}: Error fetching orderbook for {token}: {str(e)}")

    async def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        """Отримання ордербука для вказаного символу"""
        try:
            logger.info(f"Getting orderbook for {symbol} on TradeOgre")
            endpoint = self.get_endpoint_url(symbol.replace('USDT', ''))
            logger.info(f"Generated endpoint URL: {endpoint}")
            
            response = await self.http_client.get(endpoint)
            logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Raw response from TradeOgre: {data}")
            
            if 'success' in data and not data['success']:
                logger.error(f"{self.name}: API error: {data.get('error', 'Unknown error')}")
                return None
                
            # Конвертуємо дані в правильний формат
            try:
                # Для sell ордерів беремо тільки ті, що мають ненульову кількість
                asks = [[float(price), float(amount)] for price, amount in data.get('sell', {}).items() if float(amount) > 0]
                # Для buy ордерів беремо тільки ті, що мають ненульову кількість
                bids = [[float(price), float(amount)] for price, amount in data.get('buy', {}).items() if float(amount) > 0]
                
                # Сортуємо ордери
                asks.sort(key=lambda x: float(x[0]))  # Сортування за зростанням ціни
                bids.sort(key=lambda x: float(x[0]), reverse=True)  # Сортування за спаданням ціни
                
                logger.info(f"Converted orders - asks: {len(asks)}, bids: {len(bids)}")
                if asks:
                    logger.info(f"Sample asks: {asks[:3]}")
                if bids:
                    logger.info(f"Sample bids: {bids[:3]}")
                    
                return {
                    'asks': asks,
                    'bids': bids
                }
                
            except Exception as e:
                logger.error(f"Error converting order data: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {symbol} on TradeOgre: {str(e)}")
            return None

    def get_best_prices(self, token: str, threshold: float = 5.0) -> tuple:
        if token not in self.orderbooks:
            return "X X X", "X X X"
        orderbook = self.orderbooks[token]
        asks = orderbook.get('asks', [])
        bids = orderbook.get('bids', [])
        if not asks or not bids:
            return "X X X", "X X X"
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