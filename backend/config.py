"""
Конфігураційний файл для бекенду.
"""

# Базовий список токенів для початку роботи
TOKENS = [
    "BTC",
    "ETH",
    "XMR",
    "SOL",
    "DOGE"
]

# Початкові налаштування для бірж
EXCHANGES = [
    {
        "name": "MEXC",
        "url": "wss://wbs.mexc.com/raw/ws",
        "type": "websocket",
        "config": {}
    },
    {
        "name": "CoinEx",
        "url": "wss://ws.coinex.com/",
        "type": "websocket",
        "config": {}
    },
    {
        "name": "TradeOgre",
        "url": "https://tradeogre.com/api/v1",
        "type": "http",
        "config": {
            "endpoint_template": "$URL/orders/$TOKEN-USDT",
            "polling_interval": 5,
            "timeout": 10,
            "max_retries": 3,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        }
    }
]

# Інтервал опитування для HTTP-бірж (у секундах)
POLLING_INTERVAL = 5

# Поріг для розрахунку кумулятивного обсягу (в USDT)
CUMULATIVE_THRESHOLD = 5.0

# Налаштування бази даних
DATABASE_URL = "sqlite:///./crypto_orderbook.db"

# Налаштування WebSocket-сервера
WS_PING_INTERVAL = 30  # секунди між пінгами для перевірки з'єднання

# Налаштування системи логування
LOG_LEVEL = "DEBUG"
LOG_FILE = "crypto_orderbook.log"
LOG_MAX_SIZE = 5 * 1024 * 1024  # 5 МБ
LOG_BACKUPS = 3  # Кількість файлів резервного копіювання

# Налаштування для повторних спроб підключення
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5  # секунди