# /Users/tiarasabrina/Documents/PROJECT/dashboard-people-counter/backend/app/routers/video.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import cv2
import numpy as np
import sys
import asyncio
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime  # <-- ADDED

# --- System path setup ---
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.video_stream import VideoStreamHandler
from core.detector import YOLODetector
from core.tracker import ObjectTracker
from core.polygon import PolygonManager
from app.config import settings
from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["Video Stream"])

# --- Global instances ---
video_handler = None
detector = None
tracker = None
polygon_manager = None
executor = ThreadPoolExecutor(max_workers=2)

# --- Counters & state ---
enter_count = 0
exit_count = 0
current_inside = 0
prev_inside_state = {}  # {track_id: bool}


async def get_instances(db):
    """Get or create service instances"""
    global video_handler, detector, tracker, polygon_manager

    if video_handler is None:
        video_handler = VideoStreamHandler(settings.STREAM_URL)
        video_handler.start()

    if detector is None:
        detector = YOLODetector(settings.MODEL_PATH)

    if tracker is None:
        tracker = ObjectTracker(max_disappeared=settings.MAX_DISAPPEARED)

    if polygon_manager is None:
        polygon_config = await db[settings.COLLECTION_POLYGON].find_one(
            {"area_name": settings.DEFAULT_POLYGON_NAME}
        )
        if polygon_config:
            coords = polygon_config["coordinates"]
        else:
            coords = settings.get_polygon_coords()
        polygon_manager = PolygonManager(coords, settings.DEFAULT_POLYGON_NAME)

    return video_handler, detector, tracker, polygon_manager


async def _save_counting_event(db, track_id: int, event_type: str):
    """Non-blocking insert for entry/exit events"""
    try:
        doc = {
            "track_id": int(track_id),
            "event_type": event_type,          # "entry" | "exit"
            "timestamp": datetime.utcnow(),
            "area_name": settings.DEFAULT_POLYGON_NAME,
        }
        await db[settings.COLLECTION_COUNTING].insert_one(doc)
    except Exception as e:
        logger.error(f"Failed to save counting event: {e}")


async def _save_detection(db, track_id: int, bbox: list, in_polygon: bool, conf: float):
    """Optional: save per-frame detection (dipakai kalau dashboardmu baca ini)"""
    try:
        doc = {
            "track_id": int(track_id),
            "timestamp": datetime.utcnow(),
            "bbox": bbox,                      # [x1,y1,x2,y2]
            "in_polygon": bool(in_polygon),
            "area_name": settings.DEFAULT_POLYGON_NAME,
            "confidence": float(conf),
        }
        await db[settings.COLLECTION_DETECTIONS].insert_one(doc)
    except Exception as e:
        logger.error(f"Failed to save detection: {e}")


def _draw_polygon(frame, polygon_coords):
    """Draw polygon with light fill."""
    if polygon_coords and len(polygon_coords) >= 3:
        pts = np.array(polygon_coords, dtype=np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], (0, 255, 0))
        cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)


def draw_detections_on_frame(frame, tracked_detections, poly_mgr: PolygonManager, trk: ObjectTracker, db_ref):
    """
    Draw bbox, trajectory lines from tracker's history, and counters panel.
    Also updates enter/exit/current counters based on polygon membership
    and persists events to MongoDB.
    """
    global enter_count, exit_count, current_inside, prev_inside_state

    # polygon
    _draw_polygon(frame, poly_mgr.get_coordinates() if poly_mgr else [])

    # process tracks
    for det in tracked_detections:
        if len(det) < 6:
            continue

        x1, y1, x2, y2, conf, track_id = det
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # inside by polygon center
        in_polygon = False
        if poly_mgr and poly_mgr.polygon is not None:
            in_polygon = poly_mgr.is_point_inside(cx, cy)

        # transitions + DB persist (entry/exit)
        prev = prev_inside_state.get(track_id)
        if prev is None:
            prev_inside_state[track_id] = in_polygon
            if in_polygon:
                current_inside += 1
        else:
            if prev is False and in_polygon is True:
                enter_count += 1
                current_inside += 1
                prev_inside_state[track_id] = True
                # save event
                loop = asyncio.get_event_loop()
                loop.create_task(_save_counting_event(db_ref, track_id, "entry"))
            elif prev is True and in_polygon is False:
                exit_count += 1
                current_inside = max(0, current_inside - 1)
                prev_inside_state[track_id] = False
                loop = asyncio.get_event_loop()
                loop.create_task(_save_counting_event(db_ref, track_id, "exit"))

        # draw bbox + label
        color = (0, 255, 0) if in_polygon else (255, 0, 0)  # green=IN, blue=OUT
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{int(track_id)} {'IN' if in_polygon else 'OUT'} ({conf:.2f})"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(frame, label, (x1 + 3, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # centroid
        cv2.circle(frame, (cx, cy), 4, color, -1)

        # trajectory (gunakan history dari tracker)
        if hasattr(trk, "track_history"):
            pts = list(trk.track_history.get(track_id, []))
            if len(pts) > 1:
                for i in range(1, len(pts)):
                    p1 = tuple(map(int, pts[i - 1]))
                    p2 = tuple(map(int, pts[i]))
                    thickness = 2 + int(3 * (i / len(pts)))
                    cv2.line(frame, p1, p2, (0, 255, 255), thickness)

        # optional: simpan deteksi raw (bisa kamu matikan kalau DB membengkak)
        loop = asyncio.get_event_loop()
        loop.create_task(_save_detection(
            db_ref, track_id, [x1, y1, x2, y2], in_polygon, conf
        ))

    # counters panel
    panel_w, panel_h = 330, 140
    cv2.rectangle(frame, (12, 12), (12 + panel_w, 12 + panel_h), (0, 0, 0), -1)
    cv2.putText(frame, f"Enter : {enter_count}", (24, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 3)
    cv2.putText(frame, f"Exit  : {exit_count}", (24, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
    cv2.putText(frame, f"Inside: {current_inside}", (24, 136),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 3)

    return frame


def read_frame_sync(v_handler):
    """Synchronous frame reading to run in executor"""
    return v_handler.read()


async def generate_frames(db):
    """Generate video frames asynchronously"""
    v_handler, det, trk, poly = await get_instances(db)
    frame_count = 0

    while True:
        try:
            loop = asyncio.get_event_loop()
            frame = await loop.run_in_executor(executor, read_frame_sync, v_handler)

            if frame is None:
                await asyncio.sleep(0.05)
                continue

            frame_count += 1
            frame = cv2.resize(frame, (settings.FRAME_WIDTH, settings.FRAME_HEIGHT))

            if frame_count % settings.FRAME_SKIP == 0:
                detections = det.detect(frame)
                tracked_detections = trk.get_tracks_with_boxes(detections)
                frame = draw_detections_on_frame(frame, tracked_detections, poly, trk, db)

            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                await asyncio.sleep(0.01)
                continue

            frame_bytes = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

            await asyncio.sleep(0.03)

        except Exception as e:
            logger.error(f"Error generating frame: {e}", exc_info=True)
            await asyncio.sleep(0.1)
            continue


@router.get("/stream")
async def video_stream(db=Depends(get_database)):
    """Stream live video with detections + trajectories + counters"""
    return StreamingResponse(
        generate_frames(db),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/snapshot")
async def get_snapshot(db=Depends(get_database)):
    """Get single frame snapshot"""
    v_handler, _, _, _ = await get_instances(db)
    loop = asyncio.get_event_loop()
    frame = await loop.run_in_executor(executor, read_frame_sync, v_handler)

    if frame is None:
        return {"error": "No frame available"}

    frame = cv2.resize(frame, (settings.FRAME_WIDTH, settings.FRAME_HEIGHT))
    ret, buffer = cv2.imencode(".jpg", frame)
    if not ret:
        return {"error": "Failed to encode frame"}

    return StreamingResponse(iter([buffer.tobytes()]), media_type="image/jpeg")
