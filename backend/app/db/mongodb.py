from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client = None
db = None

async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB]

async def close_db():
    if client:
        client.close()

def get_db():
    """Get database instance"""
    if db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return db