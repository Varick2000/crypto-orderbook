import asyncio
from exchange_clients.xeggex import XeggexClient

async def main():
    client = XeggexClient()
    
    # Додаємо токен для спостереження
    await client.add_token("XRG/USDT")
    
    # Запускаємо з'єднання з WebSocket в окремій таскі
    connection_task = asyncio.create_task(client.connect())
    
    # Чекаємо трохи, щоб отримати перші дані
    await asyncio.sleep(5)
    
    try:
        while True:
            # Отримуємо поточний стан ордербуку
            orderbook = client.get_orderbook("XRG/USDT")
            
            print("\nBids:")
            for price, amount in orderbook["bids"][:5]:  # Показуємо перші 5 ордерів
                print(f"Price: {price}, Amount: {amount}")
                
            print("\nAsks:")
            for price, amount in orderbook["asks"][:5]:  # Показуємо перші 5 ордерів
                print(f"Price: {price}, Amount: {amount}")
                
            await asyncio.sleep(5)  # Оновлюємо кожні 5 секунд
            
    except KeyboardInterrupt:
        print("\nЗавершення роботи...")
        await client.disconnect()
        connection_task.cancel()
        
if __name__ == "__main__":
    asyncio.run(main()) 