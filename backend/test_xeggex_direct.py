import asyncio
import websockets
import json
import ssl

async def test_xeggex_connection():
    uri = "wss://api.xeggex.com/ws/v2"
    symbol = "XRG/USDT"
    
    try:
        # Створюємо SSL контекст
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        print(f"Attempting to connect to {uri}...")
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print(f"Connected to {uri}")
            
            # Відправляємо повідомлення про підписку
            subscribe_message = {
                "jsonrpc": "2.0",
                "method": "subscribeOrderbook",
                "params": {
                    "symbol": symbol
                },
                "id": 123
            }
            print(f"Sending subscribe message: {subscribe_message}")
            await websocket.send(json.dumps(subscribe_message))
            
            # Очікуємо відповідь
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    print(f"Received message type: {data.get('method', 'unknown')}")
                    
                    if "method" in data and data["method"] == "snapshotOrderbook":
                        print("\nOrderbook snapshot received!")
                        asks = data['params']['asks']
                        print(f"\nTotal asks: {len(asks)}")
                        print("\nFirst 5 asks (price, quantity):")
                        for ask in asks[:5]:
                            print(f"{ask['price']}, {ask['quantity']}")
                            
                        bids = data['params'].get('bids', [])
                        print(f"\nTotal bids: {len(bids)}")
                        print("\nFirst 5 bids (price, quantity):")
                        for bid in bids[:5]:
                            print(f"{bid['price']}, {bid['quantity']}")
                        break
                    elif "error" in data:
                        print(f"Error from server: {data['error']}")
                        break
                except Exception as e:
                    print(f"Error processing message: {str(e)}")
                    break
                    
    except Exception as e:
        print(f"Connection error: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_xeggex_connection()) 