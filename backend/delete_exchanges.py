import asyncio
import aiosqlite

async def delete_exchanges():
    async with aiosqlite.connect('../crypto_orderbook.db') as db:
        await db.execute('DROP TABLE IF EXISTS exchanges')
        await db.commit()
        print("Table 'exchanges' deleted successfully")

if __name__ == "__main__":
    asyncio.run(delete_exchanges()) 