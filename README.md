# Crypto Orderbook WebSocket API

Веб-додаток для відображення ордербуків криптовалютних бірж у реальному часі.

## Функціональність

- Підключення до різних криптовалютних бірж через WebSocket та HTTP API
- Відображення ордербуків у реальному часі
- Підтримка різних токенів (BTC, ETH, XMR, SOL, DOGE)
- Автоматичне перепідключення при втраті з'єднання
- Збереження налаштувань у базі даних SQLite

## Вимоги

- Python 3.8+
- pip (менеджер пакетів Python)

## Встановлення

1. Клонуйте репозиторій:
```bash
git clone https://github.com/yourusername/crypto-orderbook.git
cd crypto-orderbook
```

2. Створіть віртуальне середовище та активуйте його:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Встановіть залежності:
```bash
pip install -r requirements.txt
```

## Запуск

1. Запустіть бекенд:
```bash
cd backend
python app.py
```

2. Відкрийте веб-інтерфейс у браузері:
```
http://localhost:8000
```

## Структура проекту

```
crypto-orderbook/
├── backend/
│   ├── app.py              # Основний файл FastAPI додатку
│   ├── config.py           # Конфігурація
│   ├── database/
│   │   └── db.py          # Робота з базою даних
│   ├── exchange_clients/
│   │   ├── base_client.py # Базовий клас для клієнтів бірж
│   │   ├── coinex.py      # Клієнт для CoinEx
│   │   ├── mexc.py        # Клієнт для MEXC
│   │   └── tradeogre.py   # Клієнт для TradeOgre
│   └── services/
│       ├── orderbook_manager.py  # Менеджер ордербуків
│       └── websocket_manager.py  # Менеджер WebSocket з'єднань
├── frontend/
│   └── simple.html         # Веб-інтерфейс
├── requirements.txt        # Залежності проекту
└── README.md              # Документація
```

## API Endpoints

### WebSocket API

- `ws://localhost:8000/ws` - WebSocket endpoint для отримання даних у реальному часі

### REST API

- `GET /api/tokens` - Отримання списку токенів
- `POST /api/tokens` - Додавання нового токена
- `DELETE /api/tokens/{token}` - Видалення токена
- `GET /api/exchanges` - Отримання списку бірж
- `POST /api/exchanges` - Додавання нової біржі
- `DELETE /api/exchanges/{exchange}` - Видалення біржі

## Ліцензія

MIT