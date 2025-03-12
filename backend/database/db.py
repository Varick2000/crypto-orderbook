"""
Модуль для роботи з базою даних.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

import aiosqlite
from config import TOKENS, EXCHANGES

# Шлях до бази даних
DB_PATH = "crypto_orderbook.db"

# Налаштування логгера
logger = logging.getLogger(__name__)


async def init_db():
    """
    Ініціалізація бази даних, створення таблиць та заповнення початковими даними.
    """
    logger.info("Initializing database...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Створення таблиць
        await db.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL
        )
        ''')
        
        await db.execute('''
        CREATE TABLE IF NOT EXISTS exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            type TEXT NOT NULL,
            config TEXT
        )
        ''')
        
        await db.commit()
        
        # Очищаємо таблиці
        await db.execute('DELETE FROM tokens')
        await db.execute('DELETE FROM exchanges')
        
        # Додавання токенів
        for token in TOKENS:
            await db.execute('INSERT INTO tokens (symbol) VALUES (?)', (token,))
            logger.info(f"Added token: {token}")
        
        # Додавання бірж
        for exchange in EXCHANGES:
            config_json = json.dumps(exchange.get('config', {}))
            await db.execute(
                'INSERT INTO exchanges (name, url, type, config) VALUES (?, ?, ?, ?)',
                (exchange['name'], exchange['url'], exchange['type'], config_json)
            )
            logger.info(f"Added exchange: {exchange['name']}")
        
        await db.commit()
        logger.info("Database initialized with default data")


async def get_tokens() -> List[str]:
    """
    Отримати список всіх токенів з бази даних.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = lambda _, row: row[0]
        cursor = await db.execute('SELECT symbol FROM tokens')
        tokens = await cursor.fetchall()
        return tokens


async def add_token(token: str) -> bool:
    """
    Додати новий токен в базу даних.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('INSERT INTO tokens (symbol) VALUES (?)', (token,))
            await db.commit()
            logger.info(f"Token {token} added to database")
            return True
    except aiosqlite.IntegrityError:
        logger.warning(f"Token {token} already exists")
        return False
    except Exception as e:
        logger.error(f"Error adding token {token}: {str(e)}")
        return False


async def remove_token(token: str) -> bool:
    """
    Видалити токен з бази даних.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('DELETE FROM tokens WHERE symbol = ?', (token,))
            await db.commit()
            logger.info(f"Token {token} removed from database")
            return True
    except Exception as e:
        logger.error(f"Error removing token {token}: {str(e)}")
        return False


async def get_exchanges() -> List[Dict[str, Any]]:
    """
    Отримати список всіх бірж з бази даних.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT name, url, type, config FROM exchanges')
        exchanges_rows = await cursor.fetchall()
        
        exchanges = []
        for row in exchanges_rows:
            exchange = {
                'name': row['name'],
                'url': row['url'],
                'type': row['type'],
                'config': json.loads(row['config']) if row['config'] else {}
            }
            exchanges.append(exchange)
            
        return exchanges


async def add_exchange(exchange_data: Dict[str, Any]) -> bool:
    """
    Додати нову біржу в базу даних.
    """
    try:
        name = exchange_data.get('name')
        url = exchange_data.get('url')
        exchange_type = exchange_data.get('type', 'websocket')
        config = exchange_data.get('config', {})
        config_json = json.dumps(config)
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT INTO exchanges (name, url, type, config) VALUES (?, ?, ?, ?)',
                (name, url, exchange_type, config_json)
            )
            await db.commit()
            logger.info(f"Exchange {name} added to database")
            return True
    except aiosqlite.IntegrityError:
        logger.warning(f"Exchange {exchange_data.get('name')} already exists")
        return False
    except Exception as e:
        logger.error(f"Error adding exchange {exchange_data.get('name')}: {str(e)}")
        return False


async def remove_exchange(exchange_name: str) -> bool:
    """
    Видалити біржу з бази даних.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('DELETE FROM exchanges WHERE name = ?', (exchange_name,))
            await db.commit()
            logger.info(f"Exchange {exchange_name} removed from database")
            return True
    except Exception as e:
        logger.error(f"Error removing exchange {exchange_name}: {str(e)}")
        return False


async def get_exchange_by_name(exchange_name: str) -> Optional[Dict[str, Any]]:
    """
    Отримати інформацію про біржу за її назвою.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT name, url, type, config FROM exchanges WHERE name = ?',
            (exchange_name,)
        )
        row = await cursor.fetchone()
        
        if row:
            return {
                'name': row['name'],
                'url': row['url'],
                'type': row['type'],
                'config': json.loads(row['config']) if row['config'] else {}
            }
        return None