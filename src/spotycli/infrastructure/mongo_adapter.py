import logging

from pymongo import InsertOne, MongoClient, UpdateOne, errors
from pymongo.synchronous.database import Database

from src.spotycli.config import AppSettings

logger = logging.getLogger("mongo")


class MongoAdapter:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.client = None
        self.db = self._connect()

    def _connect(self) -> Database:
        """Connects to MongoDB and returns the database object."""
        try:
            self.client = MongoClient(
                self.settings.mongo_url, serverSelectionTimeoutMS=5000
            )
            # self.client.admin.command("ping") # Optional: to verify connection
            return self.client[self.settings.mongo_db]
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB :: {e}")
            raise

    def _get_db(self) -> Database:
        if self.client is None or self.db is None:
            self.db = self._connect()
        return self.db

    def close_connection(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def get_data(
        self,
        collection: str,
        query_filters: dict = None,
        query_fields: list = None,
        query_sort: list = None,
    ) -> list:
        """Get data from MongoDB"""
        logger.info(
            f"Get data : {collection} with filters : {query_filters} :: Start"
        )
        db = self._get_db()
        processed_filters = query_filters if query_filters is not None else {}
        projection = {"_id": 0}
        if query_fields:
            projection.update({field: 1 for field in query_fields})

        cursor = db[collection].find(processed_filters, projection)
        if query_sort:
            cursor = cursor.sort(query_sort)
        return list(cursor)

    def save_data_mongo(
        self, data, collection_name: str, key_fields: list = None
    ) -> tuple[int, int]:
        """Save data to MongoDB in collection"""
        logger.info(f"Save data : {collection_name} : count = {len(data)} :: Start")
        db = self._get_db()

        operations = []
        for item in data:
            if key_fields:
                item_keys = {field: item[field] for field in key_fields}
                operations.append(UpdateOne(item_keys, {"$set": item}, upsert=True))
            else:
                operations.append(InsertOne(item))

        if not operations:
            logger.info(f"Save data : {collection_name} : count = 0 :: Done")
            return 0, 0
        result = db[collection_name].bulk_write(operations)
        inserted = result.upserted_count
        updated = result.matched_count
        logger.info(f"Save data : {collection_name} : {inserted=} : {updated=} :: Done")
        return inserted, updated 