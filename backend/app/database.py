from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from app.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        try:
            cls.client = AsyncIOMotorClient(settings.MONGODB_URI)
            cls.db = cls.client[settings.DATABASE_NAME]
            
            # Test connection
            await cls.client.admin.command('ping')
            logger.info("✓ MongoDB connected successfully")
            
            # Create indexes
            await cls.create_indexes()
            
            return cls.db
            
        except Exception as e:
            logger.error(f"✗ MongoDB connection error: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    async def create_indexes(cls):
        """Create database indexes"""
        try:
            # Detections indexes
            await cls.db[settings.COLLECTION_DETECTIONS].create_index(
                [("timestamp", DESCENDING)]
            )
            await cls.db[settings.COLLECTION_DETECTIONS].create_index(
                [("track_id", ASCENDING)]
            )
            await cls.db[settings.COLLECTION_DETECTIONS].create_index(
                [("area_name", ASCENDING), ("timestamp", DESCENDING)]
            )
            
            # Counting events indexes
            await cls.db[settings.COLLECTION_COUNTING].create_index(
                [("timestamp", DESCENDING)]
            )
            await cls.db[settings.COLLECTION_COUNTING].create_index(
                [("track_id", ASCENDING)]
            )
            await cls.db[settings.COLLECTION_COUNTING].create_index(
                [("event_type", ASCENDING), ("timestamp", DESCENDING)]
            )
            await cls.db[settings.COLLECTION_COUNTING].create_index(
                [("area_name", ASCENDING), ("timestamp", DESCENDING)]
            )
            
            # Polygon config indexes
            await cls.db[settings.COLLECTION_POLYGON].create_index(
                [("area_name", ASCENDING)],
                unique=True
            )
            
            logger.info("✓ Database indexes created")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    @classmethod
    def get_db(cls):
        """Get database instance"""
        return cls.db


# Dependency for FastAPI
async def get_database():
    """FastAPI dependency to get database"""
    return MongoDB.get_db()