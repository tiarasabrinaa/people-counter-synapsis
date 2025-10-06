from .stats import router as stats_router
from .config import router as config_router
from .video import router as video_router

__all__ = ['stats_router', 'config_router', 'video_router']