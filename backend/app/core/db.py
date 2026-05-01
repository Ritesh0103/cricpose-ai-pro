from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_db_name, get_mongo_url

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(get_mongo_url())
    return _client


def get_db():
    return get_client()[get_db_name()]


async def ensure_indexes() -> None:
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.reports.create_index([("user_id", 1), ("created_at", -1)])
