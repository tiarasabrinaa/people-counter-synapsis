"""
Core detection and tracking modules
"""

from .detector import YOLODetector
from .tracker import ObjectTracker
from .polygon import PolygonManager
from .video_stream import VideoStreamHandler

__all__ = [
    'YOLODetector',
    'ObjectTracker',
    'PolygonManager',
    'VideoStreamHandler'
]