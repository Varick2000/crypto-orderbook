"""
Утиліти для розрахунку арбітражних можливостей між біржами.
"""
import logging
from typing import Dict, List, Any, Tuple

# Налаштування логгера
logger = logging.getLogger(__name__)


class ArbitrageCalculator:
    """
    Клас для розрахунку арбітражних можливостей між біржами.
    """
    
    @staticmethod
    def calculate_opportunities(orderbooks: Dict[str, Dict[str, Dict[str, str]]], min_percent: float = 1.0, fee_percent: float = 0.2) -> List[Dict[str, Any]]:
        """
        Розрахунок арбітражних можливостей між біржами.
        
        Args:
            orderbooks (Dict[str, Dict[str, Dict[str, str]]]): Словник ордербуків
            min_percent (float, optional): Мінімальний відсоток прибутку. За замовчуванням 1.0.
            fee_percent (float, optional): Відсоток комісії за транзакцію. За замовчуванням 0.2.
            
        Returns:
            List[Dict[str, Any]]: Список арбітражних можливостей
        """
        opportunities = []
        
        # Коефіцієнт комісії
        fee_factor = (1 - fee_percent / 100) ** 2  # Враховуємо комісію на обох біржах
        
        # Перебираємо всі токени
        for token, exchanges in orderbooks.items():
            # Перебираємо всі пари бірж
            exchange_names = list(exchanges.keys())
            for i in range(len(exchange_names)):
                for j in range(i + 1, len(exchange_names)):
                    exchange1 = exchange_names[i]
                    exchange2 = exchange_names[j]
                    
                    # Перевірка наявності даних
                    if 'best_sell' not in exchanges[exchange1] or 'best_buy' not in exchanges[exchange1] or \
                       'best_sell' not in exchanges[exchange2] or 'best_buy' not in exchanges[exchange2]:
                        continue
                        
                    # Отримання цін
                    sell1 = exchanges[exchange1]['best_sell']
                    buy1 = exchanges[exchange1]['best_buy']
                    sell2 = exchanges[exchange2]['best_sell']
                    buy2 = exchanges[exchange2]['best_buy']
                    
                    # Перевірка на наявність даних
                    if sell1 == 'X X X' or buy1 == 'X X X' or sell2 == 'X X X' or buy2 == 'X X X':
                        continue
                        
                    try:
                        # Конвертація в числа
                        sell1_float = float(sell1)
                        buy1_float = float(buy1)
                        sell2_float = float(sell2)
                        buy2_float = float(buy2)
                        
                        # Арбітраж 1: Купити на біржі 1, продати на біржі 2
                        if buy2_float > sell1_float:
                            profit_percent = (buy2_float / sell1_float * fee_factor - 1) * 100
                            
                            if profit_percent >= min_percent:
                                opportunities.append({
                                    'token': token,
                                    'buy_exchange': exchange1,
                                    'buy_price': sell1_float,
                                    'sell_exchange': exchange2,
                                    'sell_price': buy2_float,
                                    'profit_percent': profit_percent,
                                    'profit_usdt': (buy2_float - sell1_float) * fee_factor
                                })
                                
                        # Арбітраж 2: Купити на біржі 2, продати на біржі 1
                        if buy1_float > sell2_float:
                            profit_percent = (buy1_float / sell2_float * fee_factor - 1) * 100
                            
                            if profit_percent >= min_percent:
                                opportunities.append({
                                    'token': token,
                                    'buy_exchange': exchange2,
                                    'buy_price': sell2_float,
                                    'sell_exchange': exchange1,
                                    'sell_price': buy1_float,
                                    'profit_percent': profit_percent,
                                    'profit_usdt': (buy1_float - sell2_float) * fee_factor
                                })
                    except ValueError:
                        # Якщо не вдалося конвертувати в число, пропускаємо
                        continue
        
        # Сортування за відсотком прибутку
        return sorted(opportunities, key=lambda x: x['profit_percent'], reverse=True)
    
    @staticmethod
    def calculate_volume_limited_opportunities(orderbooks: Dict[str, Dict[str, Dict[str, Any]]], volume_usdt: float = 100.0, fee_percent: float = 0.2) -> List[Dict[str, Any]]:
        """
        Розрахунок арбітражних можливостей з обмеженням на обсяг.
        
        Args:
            orderbooks (Dict[str, Dict[str, Dict[str, Any]]]): Словник ордербуків з повними даними
            volume_usdt (float, optional): Обсяг USDT для торгівлі. За замовчуванням 100.0.
            fee_percent (float, optional): Відсоток комісії за транзакцію. За замовчуванням 0.2.
            
        Returns:
            List[Dict[str, Any]]: Список арбітражних можливостей
        """
        opportunities = []
        
        # Коефіцієнт комісії
        fee_factor = (1 - fee_percent / 100) ** 2  # Враховуємо комісію на обох біржах
        
        # Перебираємо всі токени
        for token, exchanges in orderbooks.items():
            # Перебираємо всі пари бірж
            exchange_names = list(exchanges.keys())
            for i in range(len(exchange_names)):
                for j in range(i + 1, len(exchange_names)):
                    exchange1 = exchange_names[i]
                    exchange2 = exchange_names[j]
                    
                    # Перевірка наявності даних
                    if 'asks' not in exchanges[exchange1] or 'bids' not in exchanges[exchange1] or \
                       'asks' not in exchanges[exchange2] or 'bids' not in exchanges[exchange2]:
                        continue
                        
                    # Отримання ордербуків
                    asks1 = exchanges[exchange1]['asks']
                    bids1 = exchanges[exchange1]['bids']
                    asks2 = exchanges[exchange2]['asks']
                    bids2 = exchanges[exchange2]['bids']
                    
                    # Перевірка на наявність даних
                    if not asks1 or not bids1 or not asks2 or not bids2:
                        continue
                        
                    try:
                        # Розрахунок арбітражу з обмеженням на обсяг
                        # (Тут має бути більш складна логіка для реального розрахунку)
                        # Для спрощення використовуємо тільки найкращі ціни
                        
                        # Найкращі ціни на біржі 1
                        best_ask1 = float(asks1[0][0])  # Найкраща ціна продажу (ask)
                        best_bid1 = float(bids1[0][0])  # Найкраща ціна покупки (bid)
                        
                        # Найкращі ціни на біржі 2
                        best_ask2 = float(asks2[0][0])  # Найкраща ціна продажу (ask)
                        best_bid2 = float(bids2[0][0])  # Найкраща ціна покупки (bid)
                        
                        # Арбітраж 1: Купити на біржі 1, продати на біржі 2
                        if best_bid2 > best_ask1:
                            # Розрахунок максимального обсягу для арбітражу
                            max_volume = min(
                                volume_usdt / best_ask1,  # Максимальна кількість токенів, яку можна купити
                                float(asks1[0][1]),       # Доступний обсяг на біржі 1
                                float(bids2[0][1])        # Доступний обсяг на біржі 2
                            )
                            
                            profit_percent = (best_bid2 / best_ask1 * fee_factor - 1) * 100
                            profit_usdt = (best_bid2 - best_ask1) * max_volume * fee_factor
                            
                            if profit_percent > 0:
                                opportunities.append({
                                    'token': token,
                                    'buy_exchange': exchange1,
                                    'buy_price': best_ask1,
                                    'sell_exchange': exchange2,
                                    'sell_price': best_bid2,
                                    'max_volume': max_volume,
                                    'volume_usdt': max_volume * best_ask1,
                                    'profit_percent': profit_percent,
                                    'profit_usdt': profit_usdt
                                })
                                
                        # Арбітраж 2: Купити на біржі 2, продати на біржі 1
                        if best_bid1 > best_ask2:
                            # Розрахунок максимального обсягу для арбітражу
                            max_volume = min(
                                volume_usdt / best_ask2,  # Максимальна кількість токенів, яку можна купити
                                float(asks2[0][1]),       # Доступний обсяг на біржі 2
                                float(bids1[0][1])        # Доступний обсяг на біржі 1
                            )
                            
                            profit_percent = (best_bid1 / best_ask2 * fee_factor - 1) * 100
                            profit_usdt = (best_bid1 - best_ask2) * max_volume * fee_factor
                            
                            if profit_percent > 0:
                                opportunities.append({
                                    'token': token,
                                    'buy_exchange': exchange2,
                                    'buy_price': best_ask2,
                                    'sell_exchange': exchange1,
                                    'sell_price': best_bid1,
                                    'max_volume': max_volume,
                                    'volume_usdt': max_volume * best_ask2,
                                    'profit_percent': profit_percent,
                                    'profit_usdt': profit_usdt
                                })
                    except (ValueError, IndexError):
                        # Якщо не вдалося конвертувати в число або індекс поза межами, пропускаємо
                        continue
        
        # Сортування за прибутком в USDT
        return sorted(opportunities, key=lambda x: x['profit_usdt'], reverse=True)