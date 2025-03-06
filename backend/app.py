import asyncio
import json
import logging
from typing import Dict, List, Set, Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import TOKENS, EXCHANGES, POLLING_INTERVAL
from database.db import init_db, get_tokens, get_exchanges, add_token, add_exchange, remove_token, remove_exchange
from services.orderbook_manager import OrderbookManager
from services.websocket_manager import WebSocketManager

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Створення FastAPI застосунку
app = FastAPI(title="Crypto Orderbook WebSocket API")

# Налаштування CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшені слід замінити на конкретні домени
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ініціалізація менеджерів
websocket_manager = WebSocketManager()
orderbook_manager = OrderbookManager(websocket_manager)


@app.on_event("startup")
async def startup_event():
    """Виконується при запуску сервера."""
    # Ініціалізація бази даних
    await init_db()
    
    # Завантаження токенів і бірж з БД
    tokens = await get_tokens()
    exchanges = await get_exchanges()
    
    # Ініціалізація менеджера ордербуків
    await orderbook_manager.initialize(tokens, exchanges)
    
    # Запуск процесів оновлення
    asyncio.create_task(orderbook_manager.start_polling())


@app.on_event("shutdown")
async def shutdown_event():
    """Виконується при зупинці сервера."""
    await orderbook_manager.close_all_connections()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Основний WebSocket ендпоінт для клієнтів."""
    # Спочатку приймаємо з'єднання
    await websocket.accept()
    
    # Потім додаємо клієнта до списку активних з'єднань
    await websocket_manager.connect(websocket)
    
    try:
        # Відправляємо початкові дані клієнту
        initial_data = {
            "type": "initial_data",
            "tokens": await get_tokens(),
            "exchanges": await get_exchanges(),
            "orderbooks": orderbook_manager.get_all_orderbooks()
        }
        await websocket.send_text(json.dumps(initial_data))
        
        # Підписуємо клієнта на всі дані
        await websocket_manager.subscribe(websocket, [], [])
        
        # Очікуємо повідомлення від клієнта
        while True:
            data = await websocket.receive_text()
            await process_client_message(websocket, data)
            
    except WebSocketDisconnect:
        # Видаляємо клієнта зі списку активних з'єднань
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket_manager.disconnect(websocket)


async def process_client_message(websocket: WebSocket, message: str):
    """Обробка повідомлень від клієнта."""
    try:
        data = json.loads(message)
        action = data.get("action")
        
        if action == "subscribe":
            tokens = data.get("tokens", [])
            exchanges = data.get("exchanges", [])
            await websocket_manager.subscribe(websocket, tokens, exchanges)
            
        elif action == "add_token":
            token = data.get("token")
            if not token:
                await websocket.send_text(json.dumps({"type": "error", "message": "No token provided"}))
                return
                
            await add_token(token)
            await orderbook_manager.add_token(token)
            await websocket_manager.broadcast({"type": "token_added", "token": token})
            
        elif action == "remove_token":
            token = data.get("token")
            if not token:
                await websocket.send_text(json.dumps({"type": "error", "message": "No token provided"}))
                return
                
            await remove_token(token)
            await orderbook_manager.remove_token(token)
            await websocket_manager.broadcast({"type": "token_removed", "token": token})
            
        elif action == "add_exchange":
            exchange = data.get("exchange")
            url = data.get("url")
            exchange_type = data.get("type", "websocket")  # "websocket" or "http"
            
            if not exchange or not url:
                await websocket.send_text(json.dumps({"type": "error", "message": "Exchange or URL missing"}))
                return
                
            exchange_data = {"name": exchange, "url": url, "type": exchange_type}
            await add_exchange(exchange_data)
            await orderbook_manager.add_exchange(exchange_data)
            await websocket_manager.broadcast({"type": "exchange_added", "exchange": exchange_data})
            
        elif action == "remove_exchange":
            exchange = data.get("exchange")
            if not exchange:
                await websocket.send_text(json.dumps({"type": "error", "message": "No exchange provided"}))
                return
                
            await remove_exchange(exchange)
            await orderbook_manager.remove_exchange(exchange)
            await websocket_manager.broadcast({"type": "exchange_removed", "exchange": exchange})
            
        elif action == "update_prices":
            exchange = data.get("exchange")
            if exchange:
                await orderbook_manager.refresh_exchange(exchange)
            else:
                await orderbook_manager.refresh_all()
                
        elif action == "clear":
            await orderbook_manager.clear_orderbooks()
            await websocket_manager.broadcast({"type": "orderbooks_cleared"})
            
        else:
            await websocket.send_text(json.dumps({"type": "error", "message": f"Unknown action: {action}"}))
            
    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))


# REST API ендпоінти для отримання статичних даних

@app.get("/api/tokens")
async def api_get_tokens():
    """Отримання списку всіх токенів."""
    return await get_tokens()


@app.post("/api/tokens")
async def api_add_token(token_data: dict):
    """Додавання нового токену."""
    token = token_data.get("token")
    if not token:
        raise HTTPException(400, "No token provided")
        
    await add_token(token)
    await orderbook_manager.add_token(token)
    return {"status": "success", "message": f"Token {token} added"}


@app.delete("/api/tokens/{token}")
async def api_remove_token(token: str):
    """Видалення токену."""
    await remove_token(token)
    await orderbook_manager.remove_token(token)
    return {"status": "success", "message": f"Token {token} removed"}


@app.get("/api/exchanges")
async def api_get_exchanges():
    """Отримання списку всіх бірж."""
    return await get_exchanges()


@app.post("/api/exchanges")
async def api_add_exchange(exchange_data: dict):
    """Додавання нової біржі."""
    exchange = exchange_data.get("name")
    url = exchange_data.get("url")
    exchange_type = exchange_data.get("type", "websocket")
    
    if not exchange or not url:
        raise HTTPException(400, "Exchange name or URL missing")
        
    data = {"name": exchange, "url": url, "type": exchange_type}
    await add_exchange(data)
    await orderbook_manager.add_exchange(data)
    return {"status": "success", "message": f"Exchange {exchange} added"}


@app.delete("/api/exchanges/{exchange}")
async def api_remove_exchange(exchange: str):
    """Видалення біржі."""
    await remove_exchange(exchange)
    await orderbook_manager.remove_exchange(exchange)
    return {"status": "success", "message": f"Exchange {exchange} removed"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)