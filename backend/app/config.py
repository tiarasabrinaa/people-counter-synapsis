from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    PROJECT_NAME: str = "People Counting API"
    VERSION: str = "1.0.0"
    
    # CORS - Accept as string from environment
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:8080","http://127.0.0.1:3000","http://127.0.0.1:8080"]'
    
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017/"
    DATABASE_NAME: str = "people_counting_db"
    
    # Collections
    COLLECTION_DETECTIONS: str = "detections"
    COLLECTION_COUNTING: str = "counting_events"
    COLLECTION_POLYGON: str = "polygon_config"
    
    # Model Configuration
    MODEL_PATH: str = "models/best.pt"
    CONFIDENCE_THRESHOLD: float = 0.5
    IOU_THRESHOLD: float = 0.45
    
    # Video Stream
    STREAM_URL: str = "https://cctvjss.jogjakota.go.id/malioboro/Malioboro_10_Kepatihan.stream/playlist.m3u8"
    FRAME_SKIP: int = 2
    FRAME_WIDTH: int = 1280
    FRAME_HEIGHT: int = 720
    
    # Tracking
    MAX_DISAPPEARED: int = 30
    MIN_TRACK_LENGTH: int = 3
    
    # Default Polygon
    DEFAULT_POLYGON_NAME: str = "high_risk_area_1"
    DEFAULT_POLYGON_COORDS: str = "[[300,200],[900,200],[900,500],[300,500]]"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from string to list"""
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception as e:
            print(f"Warning: Failed to parse CORS_ORIGINS: {e}")
            return ["http://localhost:3000", "http://localhost:8080"]
    
    def get_polygon_coords(self):
        """Parse polygon coordinates from string"""
        try:
            return json.loads(self.DEFAULT_POLYGON_COORDS)
        except:
            return [[300, 200], [900, 200], [900, 500], [300, 500]]


settings = Settings()