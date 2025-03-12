"""
Модуль для форсованого оновлення даних CoinEx.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

from exchange_clients.coinex import CoinExClient

logger = logging.getLogger(__name__)

class CoinExForceUpdater:
    """
    Клас для примусового оновлення даних CoinEx.
    Допомагає вирішити проблему з відображенням "X X X" у фронтенді.
    """
    
    def __init__(self, coinex_client: CoinExClient, websocket_manager):
        """
        Ініціалізація модуля оновлення.
        
        Args:
            coinex_client: Клієнт CoinEx для отримання даних
            websocket_manager: Менеджер WebSocket для відправки оновлень на фронтенд
        """
        self.coinex_client = coinex_client
        self.websocket_manager = websocket_manager
        self.last_update_time: Dict[str, float] = {}
        self.update_interval = 30.0  # Інтервал оновлення в секундах
        self.retry_interval = 5.0    # Інтервал повторних спроб
        self.max_retries = 3         # Максимальна кількість спроб
        self.is_running = False
        self.update_task = None
        self._cache: Dict[str, Dict[str, Any]] = {}
        logger.info("CoinExForceUpdater ініціалізовано")
    
    async def start(self):
        """Запуск періодичного оновлення даних CoinEx."""
        if self.is_running:
            logger.warning("CoinExForceUpdater вже запущено")
            return
            
        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("CoinExForceUpdater запущено")
    
    async def stop(self):
        """Зупинка періодичного оновлення даних CoinEx."""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.update_task:
            try:
                self.update_task.cancel()
                await self.update_task
            except asyncio.CancelledError:
                pass
            self.update_task = None
        logger.info("CoinExForceUpdater зупинено")
    
    async def _update_loop(self):
        """Цикл періодичного оновлення даних CoinEx."""
        while self.is_running:
            try:
                logger.info("Запускаємо примусове оновлення даних CoinEx")
                await self._ensure_connection()
                
                tokens = self.coinex_client.tokens
                logger.info(f"Знайдено {len(tokens)} токенів для оновлення: {tokens}")
                
                update_tasks = [self._force_update_token(token) for token in tokens]
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                
                # Обробка результатів
                for token, result in zip(tokens, results):
                    if isinstance(result, Exception):
                        logger.error(f"Помилка при оновленні {token}: {str(result)}")
                    
                logger.info("Примусове оновлення даних CoinEx завершено")
            except Exception as e:
                logger.error(f"Помилка в циклі оновлення: {str(e)}")
            finally:
                await asyncio.sleep(self.update_interval)
    
    async def _ensure_connection(self) -> bool:
        """Перевірка та відновлення з'єднання з CoinEx."""
        if not self.coinex_client.is_connected:
            logger.warning("CoinEx клієнт не підключено, спроба підключення")
            for attempt in range(self.max_retries):
                try:
                    await self.coinex_client.connect()
                    return True
                except Exception as e:
                    logger.error(f"Спроба {attempt + 1}/{self.max_retries} підключення до CoinEx невдала: {str(e)}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_interval)
            return False
        return True
    
    async def force_update_all(self):
        """Примусове оновлення всіх токенів CoinEx."""
        logger.info("Примусове оновлення всіх токенів CoinEx")
        
        if not await self._ensure_connection():
            logger.error("Не вдалося підключитися до CoinEx")
            return
        
        tokens = self.coinex_client.tokens
        logger.info(f"Знайдено {len(tokens)} токенів для оновлення: {tokens}")
        
        update_tasks = [self._force_update_token(token) for token in tokens]
        await asyncio.gather(*update_tasks, return_exceptions=True)
    
    async def force_update_token(self, token: str):
        """
        Примусове оновлення конкретного токену CoinEx.
        
        Args:
            token: Символ токена для оновлення
        """
        logger.info(f"Примусове оновлення токену {token} CoinEx")
        
        if not await self._ensure_connection():
            logger.error(f"Не вдалося підключитися до CoinEx для оновлення {token}")
            return
        
        await self._force_update_token(token)
    
    async def _force_update_token(self, token: str):
        """
        Внутрішня функція для примусового оновлення токену.
        
        Args:
            token: Символ токена для оновлення
        """
        try:
            current_time = time.time()
            last_update = self.last_update_time.get(token, 0)
            
            # Перевірка кешу та часу останнього оновлення
            if current_time - last_update < self.update_interval / 2:
                cached_data = self._cache.get(token)
                if cached_data and self._is_valid_price_data(cached_data):
                    logger.info(f"Використовуємо кешовані дані для {token}")
                    await self._broadcast_update(token, cached_data)
                    return
            
            logger.info(f"Примусове оновлення токену {token}")
            
            best_sell, best_buy = await self.coinex_client.get_best_prices(token)
            if self._is_valid_prices(best_sell, best_buy):
                update_data = {
                    'best_sell': best_sell,
                    'best_buy': best_buy,
                    'timestamp': current_time
                }
                
                # Оновлюємо кеш та час
                self._cache[token] = update_data
                self.last_update_time[token] = current_time
                
                await self._broadcast_update(token, update_data)
                logger.info(f"Успішно оновлено дані для {token}")
            else:
                logger.warning(f"Отримано невалідні ціни для {token}: sell={best_sell}, buy={best_buy}")
        except Exception as e:
            logger.error(f"Помилка при оновленні токену {token}: {str(e)}")
            raise
    
    def _is_valid_prices(self, best_sell: str, best_buy: str) -> bool:
        """Перевірка валідності цін."""
        return (best_sell and best_buy and 
                best_sell != 'X X X' and best_buy != 'X X X' and
                best_sell != '0.0' and best_buy != '0.0')
    
    def _is_valid_price_data(self, data: Dict[str, Any]) -> bool:
        """Перевірка валідності даних цін."""
        return (data and 
                self._is_valid_prices(data.get('best_sell'), data.get('best_buy')) and
                time.time() - data.get('timestamp', 0) < self.update_interval)
    
    async def _broadcast_update(self, token: str, data: Dict[str, Any]):
        """Відправка оновлення через WebSocket."""
        await self.websocket_manager.broadcast({
            'type': 'orderbook_update',
            'exchange': 'CoinEx',
            'token': token,
            'best_sell': data['best_sell'],
            'best_buy': data['best_buy']
        })
    
    async def _get_token_prices(self, token: str) -> Tuple[str, str]:
        """
        Отримання цін для токену з різних джерел.
        
        Args:
            token: Символ токена
            
        Returns:
            tuple: (best_sell, best_buy) - найкращі ціни продажу і покупки
        """
        for attempt in range(self.max_retries):
            try:
                # Спроба 1: get_best_prices
                best_sell, best_buy = await self.coinex_client.get_best_prices(token)
                if self._is_valid_prices(best_sell, best_buy):
                    return best_sell, best_buy
                
                # Спроба 2: get_orderbook
                orderbook = await self.coinex_client.get_orderbook(token)
                if orderbook:
                    best_sell = orderbook.get('best_sell')
                    best_buy = orderbook.get('best_buy')
                    if self._is_valid_prices(best_sell, best_buy):
                        return best_sell, best_buy
                
                # Спроба 3: прямий доступ до ордербуку
                symbol = f"{token}USDT"
                if symbol in self.coinex_client.orderbooks:
                    orderbook_data = self.coinex_client.orderbooks[symbol]
                    asks = orderbook_data.get('asks', [])
                    bids = orderbook_data.get('bids', [])
                    
                    if asks and bids:
                        best_sell = self.coinex_client._format_price(float(asks[0][0]))
                        best_buy = self.coinex_client._format_price(float(bids[0][0]))
                        if self._is_valid_prices(best_sell, best_buy):
                            return best_sell, best_buy
                
                if attempt < self.max_retries - 1:
                    logger.warning(f"Спроба {attempt + 1} отримання цін для {token} невдала, очікування...")
                    await asyncio.sleep(self.retry_interval)
                
            except Exception as e:
                logger.error(f"Помилка при отриманні цін для {token} (спроба {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_interval)
        
        # Якщо всі спроби невдалі, повертаємо базові значення
        logger.error(f"Всі спроби отримання цін для {token} невдалі")
        return "0.0", "0.0" 