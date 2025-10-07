from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from app.database import get_database
from app.config import settings
from models import (
    StatsResponse,
    LiveStats,
    CountSummary,
    HourlyStats,            # kita tetap pakai schema ini; field "hour" akan berisi menit yg ditruncate
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
    start_time: Optional[datetime] = Query(None, description="Start time (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End time (UTC)"),
    area_name: Optional[str] = Query(None, description="Filter by area name"),
    hours: Optional[int] = Query(24, ge=1, le=720, description="Hours to look back if no start_time"),
    include_hourly: bool = Query(True, description="Include time-bucket breakdown"),
    # NEW: granularity & minutes
    granularity: str = Query("hour", regex="^(hour|minute)$", description="Aggregation granularity"),
    minutes: Optional[int] = Query(60, ge=1, le=3600, description="If granularity=minute and no start_time, look back N minutes"),
    db=Depends(get_database)
):
    """
    Get statistics for people counting.

    - **granularity**: "hour" (default) atau "minute" untuk breakdown per-menit
    - **minutes**: dipakai jika granularity=minute dan start_time tidak diberikan
    """
    try:
        # Set time range
        if end_time is None:
            end_time = datetime.utcnow()

        if start_time is None:
            if granularity == "minute":
                lookback = minutes if minutes is not None else 60
                start_time = end_time - timedelta(minutes=lookback)
            else:
                start_time = end_time - timedelta(hours=hours or 24)

        # Build match filter
        match_filter = {
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }
        if area_name:
            match_filter["area_name"] = area_name

        # Summary (entry/exit total dalam window)
        pipeline_summary = [
            {"$match": match_filter},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
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

        # Total detections & unique tracks
        total_detections = await db[settings.COLLECTION_DETECTIONS].count_documents(match_filter)
        unique_tracks = await db[settings.COLLECTION_DETECTIONS].distinct("track_id", match_filter)

        summary = CountSummary(
            entry_count=entry_count,
            exit_count=exit_count,
            net_count=net_count,
            area_name=area_name,
            start_time=start_time,
            end_time=end_time
        )

        hourly_data: Optional[List[HourlyStats]] = None
        if include_hourly:
            hourly_data = await _get_time_stats(db, match_filter, granularity)

        return StatsResponse(
            summary=summary,
            hourly_data=hourly_data,
            total_detections=total_detections,
            unique_tracks=len(unique_tracks)
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _get_time_stats(db, match_filter: dict, granularity: str) -> List[HourlyStats]:
    """
    Breakdown count by time bucket (hour or minute).
    NOTE: kita tetap kembalikan schema HourlyStats,
    field 'hour' akan berisi waktu yang sudah di-truncate ke jam / menit (UTC).
    """
    try:
        unit = "hour" if granularity == "hour" else "minute"

        # MongoDB 6: gunakan $dateTrunc agar hasilnya Date (bukan string)
        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": {
                        "t": {
                            "$dateTrunc": {
                                "date": "$timestamp",
                                "unit": unit
                            }
                        },
                        "event_type": "$event_type"
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id.t": 1}}
        ]

        results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline).to_list(None)

        # Gabungkan entry/exit per-bucket waktu
        buckets = {}
        for r in results:
            t = r["_id"]["t"]  # datetime UTC (truncated)
            event_type = r["_id"]["event_type"]
            if t not in buckets:
                buckets[t] = {"entry": 0, "exit": 0}
            buckets[t][event_type] = r["count"]

        # Konversi ke list sesuai model
        out: List[HourlyStats] = []
        for t, counts in sorted(buckets.items(), key=lambda kv: kv[0]):
            out.append(HourlyStats(
                hour=t,  # isinya minute/hour bucket
                entry_count=counts.get("entry", 0),
                exit_count=counts.get("exit", 0),
                net_count=counts.get("entry", 0) - counts.get("exit", 0)
            ))

        return out

    except Exception as e:
        logger.error(f"Error getting time stats: {e}", exc_info=True)
        return []


@router.get("/live", response_model=LiveStats)
async def get_live_stats(
    area_name: Optional[str] = Query(None, description="Filter by area name"),
    db=Depends(get_database)
):
    """Live stats (last 5 minutes)"""
    try:
        current_time = datetime.utcnow()
        five_min_ago = current_time - timedelta(minutes=5)

        match_filter = {"timestamp": {"$gte": five_min_ago, "$lte": current_time}}
        if area_name:
            match_filter["area_name"] = area_name

        # recent entries/exits
        pipeline = [
            {"$match": match_filter},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
        ]
        results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline).to_list(None)

        recent_entries = 0
        recent_exits = 0
        for r in results:
            if r["_id"] == "entry":
                recent_entries = r["count"]
            elif r["_id"] == "exit":
                recent_exits = r["count"]

        # net all time
        all_time_filter = {}
        if area_name:
            all_time_filter["area_name"] = area_name

        pipeline_total = [
            {"$match": all_time_filter},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
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

        active_tracks = await db[settings.COLLECTION_DETECTIONS].distinct("track_id", match_filter)

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
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    area_name: Optional[str] = Query(None),
    track_id: Optional[int] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db=Depends(get_database)
):
    """Get detection records with pagination and filtering"""
    try:
        match_filter = {}
        if area_name:
            match_filter["area_name"] = area_name
        if track_id is not None:
            match_filter["track_id"] = track_id
        if start_time or end_time:
            tf = {}
            if start_time: tf["$gte"] = start_time
            if end_time: tf["$lte"] = end_time
            match_filter["timestamp"] = tf

        cursor = db[settings.COLLECTION_DETECTIONS].find(match_filter).sort("timestamp", -1).skip(skip).limit(limit)
        detections = await cursor.to_list(length=limit)
        for det in detections:
            det["_id"] = str(det["_id"])
        return detections

    except Exception as e:
        logger.error(f"Error getting detections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events", response_model=List[CountingEventResponse])
async def get_counting_events(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    area_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, regex="^(entry|exit)$"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db=Depends(get_database)
):
    """Get counting events with pagination and filtering"""
    try:
        match_filter = {}
        if area_name:
            match_filter["area_name"] = area_name
        if event_type:
            match_filter["event_type"] = event_type
        if start_time or end_time:
            tf = {}
            if start_time: tf["$gte"] = start_time
            if end_time: tf["$lte"] = end_time
            match_filter["timestamp"] = tf

        cursor = db[settings.COLLECTION_COUNTING].find(match_filter).sort("timestamp", -1).skip(skip).limit(limit)
        events = await cursor.to_list(length=limit)
        for ev in events:
            ev["_id"] = str(ev["_id"])
        return events

    except Exception as e:
        logger.error(f"Error getting counting events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest,
    db=Depends(get_database)
):
    """Generate forecasting predictions"""
    try:
        forecasting_service = ForecastingService()
        forecast_data = await forecasting_service.generate_forecast(
            db=db,
            area_name=request.area_name,
            periods=request.periods
        )
        forecast_points = [ForecastPoint(**point) for point in forecast_data]
        return ForecastResponse(
            area_name=request.area_name or "all_areas",
            forecast=forecast_points,
            model_type="prophet" if forecasting_service.model else "simple_moving_average"
        )

    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
