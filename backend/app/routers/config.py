from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from typing import List
from app.database import get_database
from app.config import settings
from models import (
    PolygonConfig,
    PolygonConfigResponse,
    PolygonConfigUpdate,
    MessageResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("/areas", response_model=List[PolygonConfigResponse])
async def get_all_areas(db=Depends(get_database)):
    """Get all polygon area configurations"""
    try:
        cursor = db[settings.COLLECTION_POLYGON].find({})
        areas = await cursor.to_list(length=100)
        return areas
    except Exception as e:
        logger.error(f"Error getting areas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/area/{area_name}", response_model=PolygonConfigResponse)
async def get_area(area_name: str, db=Depends(get_database)):
    """Get specific polygon area configuration"""
    try:
        area = await db[settings.COLLECTION_POLYGON].find_one({"area_name": area_name})
        if not area:
            raise HTTPException(status_code=404, detail=f"Area '{area_name}' not found")
        return area
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting area: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/area", response_model=PolygonConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_area(config: PolygonConfig, db=Depends(get_database)):
    """Create new polygon area configuration"""
    try:
        existing = await db[settings.COLLECTION_POLYGON].find_one({"area_name": config.area_name})
        if existing:
            raise HTTPException(status_code=400, detail=f"Area '{config.area_name}' already exists")

        doc = config.dict()
        doc["created_at"] = datetime.utcnow()
        doc["updated_at"] = datetime.utcnow()

        result = await db[settings.COLLECTION_POLYGON].insert_one(doc)
        created = await db[settings.COLLECTION_POLYGON].find_one({"_id": result.inserted_id})

        logger.info(f"Created area: {config.area_name}")
        return created
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating area: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/area/{area_name}", response_model=PolygonConfigResponse)
async def update_area(area_name: str, config: PolygonConfigUpdate, db=Depends(get_database)):
    """
    Update polygon area configuration
    Force-update updated_at field to trigger YOLO reload.
    """
    try:
        existing = await db[settings.COLLECTION_POLYGON].find_one({"area_name": area_name})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Area '{area_name}' not found")

        # Tambahkan ini: paksa waktu update agar YOLO deteksi
        update_doc = {
            "coordinates": config.coordinates,
            "updated_at": datetime.utcnow()  # <--- penting banget
        }

        if config.description is not None:
            update_doc["description"] = config.description

        # Paksa overwrite langsung (pastikan data benar-benar commit)
        await db[settings.COLLECTION_POLYGON].update_one(
            {"area_name": area_name},
            {"$set": update_doc}
        )

        # 🔥 Tambahkan sedikit delay agar periodic checker sempat baca waktu baru
        await db.command("ping")  # sekadar sync operasi DB

        updated = await db[settings.COLLECTION_POLYGON].find_one({"area_name": area_name})
        logger.info(f"✅ Polygon updated and timestamp refreshed for: {area_name}")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating area: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/area/{area_name}", response_model=MessageResponse)
async def delete_area(area_name: str, db=Depends(get_database)):
    """Delete polygon area configuration"""
    try:
        existing = await db[settings.COLLECTION_POLYGON].find_one({"area_name": area_name})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Area '{area_name}' not found")

        result = await db[settings.COLLECTION_POLYGON].delete_one({"area_name": area_name})
        logger.info(f"Deleted area: {area_name}")

        return MessageResponse(
            message=f"Area '{area_name}' deleted successfully",
            success=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting area: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/area/{area_name}/reset", response_model=MessageResponse)
async def reset_area_data(area_name: str, db=Depends(get_database)):
    """Reset detection & counting data for an area"""
    try:
        existing = await db[settings.COLLECTION_POLYGON].find_one({"area_name": area_name})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Area '{area_name}' not found")

        det_result = await db[settings.COLLECTION_DETECTIONS].delete_many({"area_name": area_name})
        count_result = await db[settings.COLLECTION_COUNTING].delete_many({"area_name": area_name})

        logger.info(f"Reset data for area: {area_name} (detections: {det_result.deleted_count}, events: {count_result.deleted_count})")

        return MessageResponse(
            message=f"Data reset for area '{area_name}'",
            success=True,
            data={
                "detections_deleted": det_result.deleted_count,
                "events_deleted": count_result.deleted_count
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting area data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
