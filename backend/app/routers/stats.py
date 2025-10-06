from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from app.database import get_database
from app.config import settings
from models import (
    StatsResponse,
    LiveStats,
    CountSummary,
    HourlyStats,
    DetectionResponse,
    CountingEventResponse,
    ForecastRequest,
    ForecastResponse,
    ForecastPoint
)
from app.services.forecasting import ForecastingService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["Statistics"])


@router.get("/", response_model=StatsResponse)
async def get_stats(
    start_time: Optional[datetime] = Query(None, description="Start time for filtering"),
    end_time: Optional[datetime] = Query(None, description="End time for filtering"),
    area_name: Optional[str] = Query(None, description="Filter by area name"),
    hours: Optional[int] = Query(24, ge=1, le=720, description="Hours to look back if no start_time"),
    include_hourly: bool = Query(True, description="Include hourly breakdown"),
    db=Depends(get_database)
):
    """
    Get statistics for people counting
    
    - **start_time**: Start time for filtering (optional)
    - **end_time**: End time for filtering (optional)
    - **hours**: Hours to look back if start_time not provided (default: 24)
    - **area_name**: Filter by specific area (optional)
    - **include_hourly**: Include hourly breakdown data (default: True)
    """
    try:
        # Set time range
        if end_time is None:
            end_time = datetime.utcnow()
        
        if start_time is None:
            start_time = end_time - timedelta(hours=hours)
        
        # Build match filter
        match_filter = {
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }
        
        if area_name:
            match_filter["area_name"] = area_name
        
        # Get counting summary
        pipeline_summary = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline_summary).to_list(None)
        
        entry_count = 0
        exit_count = 0
        
        for r in results:
            if r["_id"] == "entry":
                entry_count = r["count"]
            elif r["_id"] == "exit":
                exit_count = r["count"]
        
        net_count = entry_count - exit_count
        
        # Get total detections
        total_detections = await db[settings.COLLECTION_DETECTIONS].count_documents(match_filter)
        
        # Get unique tracks
        unique_tracks = await db[settings.COLLECTION_DETECTIONS].distinct("track_id", match_filter)
        
        # Create summary
        summary = CountSummary(
            entry_count=entry_count,
            exit_count=exit_count,
            net_count=net_count,
            area_name=area_name,
            start_time=start_time,
            end_time=end_time
        )
        
        # Get hourly breakdown if requested
        hourly_data = None
        if include_hourly:
            hourly_data = await _get_hourly_stats(db, match_filter)
        
        return StatsResponse(
            summary=summary,
            hourly_data=hourly_data,
            total_detections=total_detections,
            unique_tracks=len(unique_tracks)
        )
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_hourly_stats(db, match_filter: dict) -> List[HourlyStats]:
    """Get hourly statistics breakdown"""
    try:
        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$timestamp"},
                        "month": {"$month": "$timestamp"},
                        "day": {"$dayOfMonth": "$timestamp"},
                        "hour": {"$hour": "$timestamp"},
                        "event_type": "$event_type"
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline).to_list(None)
        
        # Group by hour
        hourly_dict = {}
        
        for r in results:
            hour_dt = datetime(
                r["_id"]["year"],
                r["_id"]["month"],
                r["_id"]["day"],
                r["_id"]["hour"]
            )
            
            if hour_dt not in hourly_dict:
                hourly_dict[hour_dt] = {"entry": 0, "exit": 0}
            
            event_type = r["_id"]["event_type"]
            hourly_dict[hour_dt][event_type] = r["count"]
        
        # Convert to list
        hourly_list = []
        for hour_dt, counts in sorted(hourly_dict.items()):
            hourly_list.append(HourlyStats(
                hour=hour_dt,
                entry_count=counts["entry"],
                exit_count=counts["exit"],
                net_count=counts["entry"] - counts["exit"]
            ))
        
        return hourly_list
        
    except Exception as e:
        logger.error(f"Error getting hourly stats: {e}")
        return []


@router.get("/live", response_model=LiveStats)
async def get_live_stats(
    area_name: Optional[str] = Query(None, description="Filter by area name"),
    db=Depends(get_database)
):
    """
    Get live statistics (last 5 minutes)
    
    - **area_name**: Filter by specific area (optional)
    """
    try:
        current_time = datetime.utcnow()
        five_min_ago = current_time - timedelta(minutes=5)
        
        # Build match filter
        match_filter = {
            "timestamp": {"$gte": five_min_ago, "$lte": current_time}
        }
        
        if area_name:
            match_filter["area_name"] = area_name
        
        # Get recent entry/exit counts
        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline).to_list(None)
        
        recent_entries = 0
        recent_exits = 0
        
        for r in results:
            if r["_id"] == "entry":
                recent_entries = r["count"]
            elif r["_id"] == "exit":
                recent_exits = r["count"]
        
        # Calculate current count (net from all time)
        all_time_filter = {}
        if area_name:
            all_time_filter["area_name"] = area_name
        
        pipeline_total = [
            {"$match": all_time_filter},
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        total_results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline_total).to_list(None)
        
        total_entries = 0
        total_exits = 0
        
        for r in total_results:
            if r["_id"] == "entry":
                total_entries = r["count"]
            elif r["_id"] == "exit":
                total_exits = r["count"]
        
        current_count = max(0, total_entries - total_exits)
        
        # Get active track IDs (last 5 minutes)
        active_tracks = await db[settings.COLLECTION_DETECTIONS].distinct(
            "track_id",
            match_filter
        )
        
        return LiveStats(
            current_count=current_count,
            recent_entries=recent_entries,
            recent_exits=recent_exits,
            active_track_ids=sorted(active_tracks),
            last_updated=current_time
        )
        
    except Exception as e:
        logger.error(f"Error getting live stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detections", response_model=List[DetectionResponse])
async def get_detections(
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    area_name: Optional[str] = Query(None, description="Filter by area name"),
    track_id: Optional[int] = Query(None, description="Filter by track ID"),
    start_time: Optional[datetime] = Query(None, description="Start time"),
    end_time: Optional[datetime] = Query(None, description="End time"),
    db=Depends(get_database)
):
    """
    Get detection records with pagination and filtering
    """
    try:
        # Build filter
        match_filter = {}
        
        if area_name:
            match_filter["area_name"] = area_name
        
        if track_id is not None:
            match_filter["track_id"] = track_id
        
        if start_time or end_time:
            time_filter = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_filter["timestamp"] = time_filter
        
        # Query database
        cursor = db[settings.COLLECTION_DETECTIONS].find(match_filter).sort("timestamp", -1).skip(skip).limit(limit)
        
        detections = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for det in detections:
            det["_id"] = str(det["_id"])
        
        return detections
        
    except Exception as e:
        logger.error(f"Error getting detections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events", response_model=List[CountingEventResponse])
async def get_counting_events(
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    area_name: Optional[str] = Query(None, description="Filter by area name"),
    event_type: Optional[str] = Query(None, description="Filter by event type (entry/exit)"),
    start_time: Optional[datetime] = Query(None, description="Start time"),
    end_time: Optional[datetime] = Query(None, description="End time"),
    db=Depends(get_database)
):
    """
    Get counting events with pagination and filtering
    """
    try:
        # Build filter
        match_filter = {}
        
        if area_name:
            match_filter["area_name"] = area_name
        
        if event_type:
            match_filter["event_type"] = event_type
        
        if start_time or end_time:
            time_filter = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_filter["timestamp"] = time_filter
        
        # Query database
        cursor = db[settings.COLLECTION_COUNTING].find(match_filter).sort("timestamp", -1).skip(skip).limit(limit)
        
        events = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for event in events:
            event["_id"] = str(event["_id"])
        
        return events
        
    except Exception as e:
        logger.error(f"Error getting counting events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest,
    db=Depends(get_database)
):
    """
    Generate forecasting predictions
    
    - **area_name**: Area to forecast (optional, defaults to all areas)
    - **periods**: Number of hours to forecast (default: 24, max: 168)
    """
    try:
        forecasting_service = ForecastingService()
        
        forecast_data = await forecasting_service.generate_forecast(
            db=db,
            area_name=request.area_name,
            periods=request.periods
        )
        
        # Convert to response format
        forecast_points = [
            ForecastPoint(**point) for point in forecast_data
        ]
        
        return ForecastResponse(
            area_name=request.area_name or "all_areas",
            forecast=forecast_points,
            model_type="prophet" if forecasting_service.model else "simple_moving_average"
        )
        
    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))