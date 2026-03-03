import json
import os
from datetime import datetime, timezone
from typing import Optional

from agno.tools import Toolkit
from agno.utils.log import log_debug, log_info, logger

try:
    from pymongo import MongoClient
except ImportError:
    raise ImportError("`pymongo` not installed. Please install using `pip install pymongo`.")


class MongoSaveTools(Toolkit):
    """Custom toolkit for saving structured data to MongoDB collections."""

    def __init__(
        self,
        db_url: Optional[str] = None,
        db_name: Optional[str] = None,
        default_collection: Optional[str] = None,
        **kwargs,
    ):
        self._db_url = db_url or os.getenv("MONGO_URL", "mongodb://localhost:27017")
        self._db_name = db_name or os.getenv("MONGO_DB_NAME", "agno_agents")
        self._default_collection = default_collection
        self._mongo_client = MongoClient(self._db_url)
        self._mongo_db = self._mongo_client[self._db_name]

        tools = [self.save_text, self.save_headline, self.query_documents]
        super().__init__(name="mongo_save", tools=tools, **kwargs)

    def save_text(self, title: str, summary: str, tags: str, collection: Optional[str] = None) -> str:
        """
        Save a text document to MongoDB. Keep arguments short.

        Args:
            title: Short title or headline for the document (under 200 chars).
            summary: A brief summary of the content (under 500 chars). Do NOT paste full articles.
            tags: Comma-separated topic tags (e.g. 'crypto,finance,breaking').
            collection: Collection name. Defaults to the configured default.

        Returns:
            Confirmation with the inserted document ID.
        """
        coll = collection or self._default_collection or "documents"
        log_debug(f"Saving text to collection: {coll}")
        try:
            doc = {
                "title": title,
                "summary": summary,
                "tags": [t.strip() for t in tags.split(",")],
                "saved_at": datetime.now(timezone.utc),
            }
            result = self._mongo_db[coll].insert_one(doc)
            log_info(f"Saved to {coll}: {result.inserted_id}")
            return json.dumps({"status": "saved", "collection": coll, "id": str(result.inserted_id)})
        except Exception as e:
            logger.error(f"Error saving to {coll}: {e}")
            return json.dumps({"error": str(e)})

    def save_headline(self, headline: str, source: str, tags: str, collection: Optional[str] = None) -> str:
        """
        Save a news headline to MongoDB. Use this for individual news items.

        Args:
            headline: The headline text (one sentence).
            source: Where it came from (e.g. 'X/@elonmusk', 'Reuters', 'web search').
            tags: Comma-separated topic tags (e.g. 'crypto,regulation').
            collection: Collection name. Defaults to the configured default.

        Returns:
            Confirmation with the inserted document ID.
        """
        coll = collection or self._default_collection or "documents"
        log_debug(f"Saving headline to collection: {coll}")
        try:
            doc = {
                "headline": headline,
                "source": source,
                "tags": [t.strip() for t in tags.split(",")],
                "saved_at": datetime.now(timezone.utc),
            }
            result = self._mongo_db[coll].insert_one(doc)
            log_info(f"Saved headline to {coll}: {result.inserted_id}")
            return json.dumps({"status": "saved", "collection": coll, "id": str(result.inserted_id)})
        except Exception as e:
            logger.error(f"Error saving to {coll}: {e}")
            return json.dumps({"error": str(e)})

    def query_documents(self, collection: str, query: Optional[str] = None, limit: int = 10) -> str:
        """
        Query recent documents from a MongoDB collection.

        Args:
            collection: The collection name to query (e.g. 'news_raw', 'news_digests').
            query: Optional search text to filter by. Searches title, headline, summary, and tags.
            limit: Maximum number of documents to return. Default 10.

        Returns:
            JSON array of matching documents, most recent first.
        """
        log_debug(f"Querying collection: {collection}, query: {query}, limit: {limit}")
        try:
            filter_query = {}
            if query:
                filter_query["$or"] = [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"headline": {"$regex": query, "$options": "i"}},
                    {"summary": {"$regex": query, "$options": "i"}},
                    {"tags": {"$regex": query, "$options": "i"}},
                    {"source": {"$regex": query, "$options": "i"}},
                ]

            cursor = self._mongo_db[collection].find(
                filter_query, {"_id": 0}
            ).sort("saved_at", -1).limit(limit)

            docs = list(cursor)
            for doc in docs:
                for k, v in doc.items():
                    if isinstance(v, datetime):
                        doc[k] = v.isoformat()

            log_info(f"Found {len(docs)} documents in {collection}")
            return json.dumps(docs, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error querying {collection}: {e}")
            return json.dumps({"error": str(e)})
