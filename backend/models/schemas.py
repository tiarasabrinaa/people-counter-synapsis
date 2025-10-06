from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional, Literal
from enum import Enum


# Enums
class EventType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


# Detection Models
class Detection(BaseModel):
    track_id: int = Field(..., description="Unique tracking ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bbox: List[int] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    in_polygon: bool = Field(..., description="Whether object is inside polygon")
    area_name: str = Field(..., description="Name of the polygon area")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Detection confidence")
    
    @validator('bbox')
    def validate_bbox(cls, v):
        if len(v) != 4:
            raise ValueError('Bounding box must have 4 coordinates')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "track_id": 1,
                "timestamp": "2025-10-05T10:30:00Z",
                "bbox": [100, 200, 300, 400],
                "in_polygon": True,
                "area_name": "high_risk_area_1",
                "confidence": 0.95
            }
        }


class DetectionResponse(Detection):
    id: Optional[str] = Field(None, alias="_id")
    
    class Config:
        populate_by_name = True


# Counting Event Models
class CountingEvent(BaseModel):
    track_id: int = Field(..., description="Unique tracking ID")
    event_type: EventType = Field(..., description="Type of event: entry or exit")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    area_name: str = Field(..., description="Name of the polygon area")
    
    class Config:
        json_schema_extra = {
            "example": {
                "track_id": 1,
                "event_type": "entry",
                "timestamp": "2025-10-05T10:30:00Z",
                "area_name": "high_risk_area_1"
            }
        }


class CountingEventResponse(CountingEvent):
    id: Optional[str] = Field(None, alias="_id")
    
    class Config:
        populate_by_name = True


# Polygon Configuration Models
class PolygonConfig(BaseModel):
    area_name: str = Field(..., description="Unique name for the area")
    coordinates: List[List[int]] = Field(..., description="Polygon coordinates [[x1,y1], [x2,y2], ...]")
    description: Optional[str] = Field(None, description="Area description")
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if len(v) < 3:
            raise ValueError('Polygon must have at least 3 points')
        for point in v:
            if len(point) != 2:
                raise ValueError('Each coordinate must have x and y values')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "area_name": "high_risk_area_1",
                "coordinates": [[100, 100], [500, 100], [500, 400], [100, 400]],
                "description": "Main entrance area"
            }
        }


class PolygonConfigResponse(PolygonConfig):
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class PolygonConfigUpdate(BaseModel):
    coordinates: List[List[int]] = Field(..., description="New polygon coordinates")
    description: Optional[str] = Field(None, description="Area description")
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if len(v) < 3:
            raise ValueError('Polygon must have at least 3 points')
        return v


# Statistics Models
class CountSummary(BaseModel):
    entry_count: int = Field(..., description="Number of entries")
    exit_count: int = Field(..., description="Number of exits")
    net_count: int = Field(..., description="Net count (entry - exit)")
    area_name: Optional[str] = Field(None, description="Area name filter")
    start_time: Optional[datetime] = Field(None, description="Start of time range")
    end_time: Optional[datetime] = Field(None, description="End of time range")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entry_count": 45,
                "exit_count": 32,
                "net_count": 13,
                "area_name": "high_risk_area_1",
                "start_time": "2025-10-05T10:00:00Z",
                "end_time": "2025-10-05T11:00:00Z"
            }
        }


class HourlyStats(BaseModel):
    hour: datetime = Field(..., description="Hour timestamp")
    entry_count: int = Field(0, description="Entries in this hour")
    exit_count: int = Field(0, description="Exits in this hour")
    net_count: int = Field(0, description="Net count for this hour")


class StatsResponse(BaseModel):
    summary: CountSummary
    hourly_data: Optional[List[HourlyStats]] = None
    total_detections: int = Field(..., description="Total detections in period")
    unique_tracks: int = Field(..., description="Number of unique track IDs")


class LiveStats(BaseModel):
    current_count: int = Field(..., description="Current people in area")
    recent_entries: int = Field(..., description="Entries in last 5 minutes")
    recent_exits: int = Field(..., description="Exits in last 5 minutes")
    active_track_ids: List[int] = Field(..., description="Currently tracked IDs")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_count": 15,
                "recent_entries": 3,
                "recent_exits": 1,
                "active_track_ids": [1, 5, 8, 12, 15],
                "last_updated": "2025-10-05T11:30:00Z"
            }
        }


# Forecasting Models
class ForecastRequest(BaseModel):
    area_name: Optional[str] = Field(None, description="Area name to forecast")
    periods: int = Field(24, ge=1, le=168, description="Number of hours to forecast")
    
    class Config:
        json_schema_extra = {
            "example": {
                "area_name": "high_risk_area_1",
                "periods": 24
            }
        }


class ForecastPoint(BaseModel):
    timestamp: datetime
    predicted_count: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastResponse(BaseModel):
    area_name: str
    forecast: List[ForecastPoint]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_type: str = Field("prophet", description="Forecasting model used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "area_name": "high_risk_area_1",
                "forecast": [
                    {
                        "timestamp": "2025-10-05T12:00:00Z",
                        "predicted_count": 25.5,
                        "lower_bound": 20.0,
                        "upper_bound": 31.0
                    }
                ],
                "generated_at": "2025-10-05T11:30:00Z",
                "model_type": "prophet"
            }
        }


# Pagination
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")


# Generic Response
class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[dict] = None