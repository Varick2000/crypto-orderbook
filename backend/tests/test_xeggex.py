import asyncio
import logging
import sys
import os
import json

# Додаємо корневу директорію проекту до PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchange_clients.xeggex import XeggexClient

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_xeggex_orderbook():
    """Тест отримання даних ордербуку від Xeggex."""
    try:
        # Створюємо клієнт
        client = XeggexClient(
            name="Xeggex",
            url="wss://api.xeggex.com/ws/v2",
            config={"ping_interval": 30}
        )
        logger.info("Створено клієнт Xeggex")
        
        # Підключаємося до WebSocket
        await client.connect()
        logger.info("Підключено до WebSocket")
        
        # Тестовий символ
        symbol = "XRG/USDT"
        
        # Відправляємо повідомлення про підписку
        subscribe_message = {
            "jsonrpc": "2.0",
            "method": "subscribeOrderbook",
            "params": {
                "symbol": symbol
            },
            "id": 123
        }
        
        logger.info(f"Відправка підписки для {symbol}")
        await client.ws.send(json.dumps(subscribe_message))
        
        # Чекаємо на отримання даних
        while True:
            try:
                message = await client.ws.recv()
                data = json.loads(message)
                logger.info(f"Отримано повідомлення типу: {data.get('method', 'unknown')}")
                
                if "method" in data and data["method"] == "snapshotOrderbook":
                    logger.info("\nОтримано снапшот ордербуку!")
                    asks = data['params']['asks']
                    logger.info(f"\nВсього asks: {len(asks)}")
                    logger.info("\nПерші 5 asks (ціна, кількість):")
                    for ask in asks[:5]:
                        logger.info(f"{ask['price']}, {ask['quantity']}")
                        
                    bids = data['params'].get('bids', [])
                    logger.info(f"\nВсього bids: {len(bids)}")
                    logger.info("\nПерші 5 bids (ціна, кількість):")
                    for bid in bids[:5]:
                        logger.info(f"{bid['price']}, {bid['quantity']}")
                    break
                elif "error" in data:
                    logger.error(f"Помилка від сервера: {data['error']}")
                    break
                    
            except Exception as e:
                logger.error(f"Помилка обробки повідомлення: {str(e)}")
                break
        
        # Закриваємо з'єднання
        await client.disconnect()
        logger.info("Закрито з'єднання")
        
    except Exception as e:
        logger.error(f"Помилка при тестуванні: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_xeggex_orderbook()) 