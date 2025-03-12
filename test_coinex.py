import asyncio
import websockets
import json
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WS_URL = "wss://ws.coinex.com/"

def process_orderbook(data):
    if "params" in data and len(data["params"]) > 1:
        orderbook = data["params"][1]
        asks = orderbook.get("asks", [])
        bids = orderbook.get("bids", [])
        
        print("\n=== Стан ордербуку ===")
        print(f"Кількість ордерів на продаж (asks): {len(asks)}")
        print(f"Кількість ордерів на купівлю (bids): {len(bids)}")
        
        if asks and bids:
            print("\nНайкращі 3 ціни продажу (asks):")
            for i, ask in enumerate(asks[:50]):
                print(f"  {i+1}. Ціна: {ask[0]} USDT, Кількість: {ask[1]} BTC")
            
            print("\nНайкращі 3 ціни купівлі (bids):")
            for i, bid in enumerate(bids[:50]):
                print(f"  {i+1}. Ціна: {bid[0]} USDT, Кількість: {bid[1]} BTC")
        print("=====================\n")

async def coinex_client():
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                logger.info("З'єднання встановлено")
                
                # Формуємо повідомлення для підписки на ордербук
                subscription = {
                    "method": "depth.subscribe",
                    "params": [
                        "BTCUSDT",
                        50,
                        "0",
                        True
                    ],
                    "id": 1
                }
                
                await ws.send(json.dumps(subscription))
                logger.info(f"Відправлено повідомлення підписки: {subscription}")
                
                while True:
                    try:
                        message = await ws.recv()
                        data = json.loads(message)
                        process_orderbook(data)
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.error(f"З'єднання закрито: {e}")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"Помилка розбору JSON: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Неочікувана помилка: {e}")
                        break
                
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"Помилка підключення: {e}")
        except Exception as e:
            logger.error(f"Критична помилка: {e}")
        
        logger.info("Очікування 5 секунд перед повторним підключенням...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(coinex_client())
    except KeyboardInterrupt:
        logger.info("Програму завершено користувачем") 