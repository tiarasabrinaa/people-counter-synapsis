# /backend/core/frame_bus.py
from threading import Lock

_latest_jpeg = None
_lock = Lock()

def set_latest_jpeg(data: bytes):
    global _latest_jpeg
    with _lock:
        _latest_jpeg = data

def get_latest_jpeg() -> bytes | None:
    with _lock:
        return _latest_jpeg
