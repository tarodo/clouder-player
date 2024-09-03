from urllib.parse import quote, urlparse, urlunparse

from environs import Env, EnvError
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


async def get_mongo_conn() -> AsyncIOMotorDatabase:
    """Connects to MongoDB and returns the database object."""
    try:
        env = Env()
        env.read_env()

        user = env.str("MONGO_USER")
        password = env.str("MONGO_PASS")
        host = env.str("MONGO_HOST")
        port = env.str("MONGO_PORT")
        db_name = env.str("MONGO_DB")
    except EnvError as e:
        raise KeyError(
            f"Environment variables for MongoDB are not set correctly. :: {e}"
        )

    try:
        url = urlparse("")
        url = url._replace(
            scheme="mongodb", netloc=f"{user}:{quote(password)}@{host}:{port}"
        )
        client = AsyncIOMotorClient(str(urlunparse(url)), serverSelectionTimeoutMS=5000)

        await client.admin.command("ping")

        return client[db_name]
    except Exception as e:
        raise Exception(f"Failed to connect to MongoDB database. :: {e}")


async def get_sp_clouder_week_by_pl_id(sp_pl_id: str) -> dict:
    """Get clouder weeks from MongoDB."""
    db = await get_mongo_conn()

    return await db.clouder_weeks.find_one(
        {f"sp_playlists.{sp_pl_id}": {"$exists": True}}
    )
