import logging

from pymongo import MongoClient
from pymongo.synchronous.database import Database

from src.spotycli.config import settings

logger = logging.getLogger("mongo")


def get_mongo_conn() -> Database:
    """Connects to MongoDB and returns the database object."""
    mongo_url = settings.mongo_url
    mongo_db = settings.mongo_db
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB :: {e}")
        raise

    try:
        # client.admin.command("ping")
        return client[mongo_db]
    except Exception as e:
        logger.error(f"Failed to check the MongoDB database. :: {e}")
        raise


def get_data(
    collection: str,
    query_filters: dict = None,
    query_fields: list = None,
    db: MongoClient = None,
) -> list:
    """Get data from MongoDB"""
    logger.info(f"Get data : {collection} with filters : {query_filters} :: Start")
    close_connection = False
    if db is None:
        db = get_mongo_conn()
        close_connection = True
    filters = {}
    filters.update(query_filters) if query_filters else filters
    fields = {"_id": 0}
    fields.update({field: 1 for field in query_fields}) if query_fields else fields
    try:
        result = list(
            db[collection].find(
                filters,
                fields,
            )
        )
        return result
    finally:
        if close_connection:
            db.client.close()
