"""
Real-time Detection Service
Runs object detection, tracking, and counting continuously
Saves results to MongoDB
"""

import cv2
import asyncio
import signal
import sys
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from collections import defaultdict, deque
import numpy as np  # >>> ADDED

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from core.detector import YOLODetector
from core.tracker import ObjectTracker
from core.polygon import PolygonManager
from core.video_stream import VideoStreamHandler
from core.frame_bus import set_latest_jpeg  # >>> ADDED

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetectionService:
    def __init__(self):
        self.detector = None
        self.tracker = None
        self.polygon_manager = None
        self.stream_handler = None
        self.db_client = None
        self.db = None
        self.running = False
        self.frame_count = 0
        self.last_polygon_update = None
        self.original_width = None
        self.original_height = None
        
        # >>> ADDED: counters + history for trajectory
        self.enter_count = 0
        self.exit_count = 0
        self.current_inside = 0
        self.track_history = defaultdict(lambda: deque(maxlen=40))
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing Detection Service...")
        
        # Initialize database
        try:
            self.db_client = AsyncIOMotorClient(settings.MONGODB_URI)
            self.db = self.db_client[settings.DATABASE_NAME]
            await self.db.command('ping')
            logger.info("✓ MongoDB connected")
        except Exception as e:
            logger.error(f"✗ MongoDB connection failed: {e}")
            raise
        
        # Initialize video stream
        try:
            self.stream_handler = VideoStreamHandler(settings.STREAM_URL)
            if self.stream_handler.start():
                logger.info("✓ Video stream started")
                await asyncio.sleep(2)
                self.original_width = int(self.stream_handler.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.original_height = int(self.stream_handler.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(f"Original video size: {self.original_width}x{self.original_height}")
            else:
                raise Exception("Failed to start video stream")
        except Exception as e:
            logger.error(f"✗ Video stream error: {e}")
            raise
        
        # Load polygon configuration
        await self.reload_polygon()
        
        # Initialize YOLO detector
        try:
            self.detector = YOLODetector(settings.MODEL_PATH)
            logger.info("✓ YOLO detector initialized")
        except Exception as e:
            logger.error(f"✗ Failed to initialize detector: {e}")
            raise
        
        # Initialize tracker
        self.tracker = ObjectTracker(max_disappeared=settings.MAX_DISAPPEARED)
        logger.info("✓ Object tracker initialized")
        
        logger.info("✓ Detection Service initialized successfully")

    async def periodic_polygon_check(self):
        """Check and reload polygon every 1 second"""
        logger.info("🔍 Periodic polygon check task STARTED")
        
        while self.running:
            try:
                await asyncio.sleep(1)
                
                polygon_config = await self.db[settings.COLLECTION_POLYGON].find_one(
                    {"area_name": settings.DEFAULT_POLYGON_NAME}
                )
                
                if polygon_config:
                    updated_at = polygon_config.get('updated_at')
                    
                    if self.last_polygon_update != updated_at:
                        coords = polygon_config['coordinates']
                        logger.info("=" * 60)
                        logger.info("⚡ POLYGON CHANGE DETECTED!")
                        logger.info(f"   New timestamp: {updated_at}")
                        logger.info(f"   New coords: {coords}")
                        
                        if self.polygon_manager is None:
                            self.polygon_manager = PolygonManager(coords, settings.DEFAULT_POLYGON_NAME)
                        else:
                            self.polygon_manager.update_polygon(
                                coords,
                                frame_size=(settings.FRAME_WIDTH, settings.FRAME_HEIGHT),
                                original_size=(self.original_width, self.original_height)
                            )
                        
                        self.last_polygon_update = updated_at
                        logger.info("✅ POLYGON RELOADED!")
                        logger.info("=" * 60)
                        
            except Exception as e:
                logger.error(f"❌ Polygon check error: {e}", exc_info=True)
        
    async def process_frame(self, frame):
        """Process single frame"""
        if frame is None:
            return None
        
        # Resize frame
        frame = cv2.resize(frame, (settings.FRAME_WIDTH, settings.FRAME_HEIGHT))
        
        # Skip frames for performance
        self.frame_count += 1
        if self.frame_count % settings.FRAME_SKIP != 0:
            # >>> ADDED: tetap publish frame terakhir (tanpa overlay) biar stream nggak freeze
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                set_latest_jpeg(buf.tobytes())
            return frame
        
        try:
            detections = self.detector.detect(frame)
            
            if len(detections) == 0:
                # >>> publish tetap
                ok, buf = cv2.imencode(".jpg", frame)
                if ok:
                    set_latest_jpeg(buf.tobytes())
                return frame
            
            # Dapatkan hasil tracking
            tracked_detections = self.tracker.get_tracks_with_boxes(detections)

            # ====== COUNTERS (poly sementara di-skip) ======
            for det in tracked_detections:
                x1, y1, x2, y2, conf, track_id = det
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                self.track_history[track_id].append((cx, cy))
                
                # Garis imajiner di tengah frame (sementara)
                mid_y = settings.FRAME_HEIGHT // 2
                if cy < mid_y and not hasattr(self.tracker, f"in_{track_id}"):
                    self.enter_count += 1
                    self.current_inside += 1
                    setattr(self.tracker, f"in_{track_id}", True)
                elif cy > mid_y and hasattr(self.tracker, f"in_{track_id}") and not hasattr(self.tracker, f"out_{track_id}"):
                    self.exit_count += 1
                    self.current_inside = max(0, self.current_inside - 1)
                    setattr(self.tracker, f"out_{track_id}", True)
                
                # Simpan deteksi (DB)
                asyncio.create_task(self.save_detection(
                    track_id=int(track_id),
                    bbox=[int(x1), int(y1), int(x2), int(y2)],
                    in_polygon=False,
                    confidence=float(conf)
                ))

            # ====== DRAW OVERLAY ke frame ======
            frame = self.draw_dashboard(frame, tracked_detections)

            # >>> ADDED: publish JPEG ke frame_bus untuk dashboard
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                set_latest_jpeg(buf.tobytes())

            return frame

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            # >>> publish last raw frame jika error
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                set_latest_jpeg(buf.tobytes())
            return frame
    
    def draw_dashboard(self, frame, tracked_detections):
        """Draw (only) polygon, boxes, id, and trajectories. No HUD counters."""
        # (optional) draw polygon if available
        if self.polygon_manager and len(self.polygon_manager.coordinates) >= 3:
            pts = np.array(self.polygon_manager.coordinates, np.int32)
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=3)

        # boxes + id + trajectory
        for x1, y1, x2, y2, conf, track_id in tracked_detections:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 255), 2)
            cv2.putText(frame, f"ID:{int(track_id)} ({conf:.2f})",
                        (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 255), 2)

            pts = self.track_history.get(track_id, [])
            if len(pts) > 1:
                for i in range(1, len(pts)):
                    cv2.line(frame, pts[i-1], pts[i], (0, 255, 255), 3)

        # —— NO HUD / NO ENTER-EXIT-INSIDE PANEL ——
        return frame

    
    async def save_detection(self, track_id: int, bbox: list, in_polygon: bool, confidence: float):
        """Save detection to database"""
        try:
            doc = {
                "track_id": track_id,
                "timestamp": datetime.utcnow(),
                "bbox": bbox,
                "in_polygon": in_polygon,
                "area_name": settings.DEFAULT_POLYGON_NAME,
                "confidence": confidence
            }
            await self.db[settings.COLLECTION_DETECTIONS].insert_one(doc)
        except Exception as e:
            logger.error(f"Error saving detection: {e}")
    
    async def save_counting_event(self, track_id: int, event_type: str):
        """Save counting event to database"""
        try:
            doc = {
                "track_id": track_id,
                "event_type": event_type,
                "timestamp": datetime.utcnow(),
                "area_name": settings.DEFAULT_POLYGON_NAME
            }
            await self.db[settings.COLLECTION_COUNTING].insert_one(doc)
        except Exception as e:
            logger.error(f"Error saving counting event: {e}")
    
    async def run(self):
        """Main detection loop"""
        self.running = True
        logger.info("🚀 Starting detection loop...")
        
        polygon_task = asyncio.create_task(self.periodic_polygon_check())
        logger.info("✓ Polygon check background task created")
        
        processed_frames = 0
        start_time = datetime.now()
        
        try:
            while self.running:
                frame = self.stream_handler.read()
                
                if frame is not None:
                    await self.process_frame(frame)
                    processed_frames += 1
                    
                    if processed_frames % 100 == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        fps = processed_frames / elapsed if elapsed > 0 else 0
                        logger.info(f"📈 Processed: {processed_frames} frames, FPS: {fps:.2f}")
                
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("⚠ Received shutdown signal")
        except Exception as e:
            logger.error(f"✗ Error in detection loop: {e}", exc_info=True)
        finally:
            polygon_task.cancel()
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up...")
        
        self.running = False
        
        if self.stream_handler:
            self.stream_handler.stop()
        
        if self.db_client:
            self.db_client.close()
        
        logger.info("✓ Cleanup complete")
    
    async def reload_polygon(self):
        """Reload polygon from database"""
        try:
            polygon_config = await self.db[settings.COLLECTION_POLYGON].find_one(
                {"area_name": settings.DEFAULT_POLYGON_NAME}
            )
            
            if polygon_config:
                coords = polygon_config['coordinates']
                updated_at = polygon_config.get('updated_at')
                
                if self.polygon_manager is None:
                    logger.info(f"✓ Loaded polygon: {settings.DEFAULT_POLYGON_NAME} with {len(coords)} points")
                    logger.info(f"  Coordinates: {coords}")
                    self.polygon_manager = PolygonManager(coords, settings.DEFAULT_POLYGON_NAME)
                    self.last_polygon_update = updated_at
                else:
                    if self.last_polygon_update != updated_at:
                        logger.info(f"🔄 POLYGON UPDATE DETECTED!")
                        self.polygon_manager.update_polygon(
                            coords,
                            frame_size=(settings.FRAME_WIDTH, settings.FRAME_HEIGHT),
                            original_size=(self.original_width, self.original_height)
                        )
                        self.last_polygon_update = updated_at
                        logger.info("✅ POLYGON SUCCESSFULLY RELOADED!")
            else:
                coords = settings.get_polygon_coords()
                logger.info(f"⚠ No polygon found in DB, creating default with {len(coords)} points")
                
                await self.db[settings.COLLECTION_POLYGON].insert_one({
                    "area_name": settings.DEFAULT_POLYGON_NAME,
                    "coordinates": coords,
                    "description": "Default high risk area",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
                
                self.polygon_manager = PolygonManager(coords, settings.DEFAULT_POLYGON_NAME)
                self.last_polygon_update = datetime.utcnow()
                logger.info("✓ Default polygon created and loaded")
            
        except Exception as e:
            logger.error(f"✗ Failed to reload polygon: {e}", exc_info=True)
            if not self.polygon_manager:
                coords = [[100, 100], [500, 100], [500, 400], [100, 400]]
                logger.warning(f"⚠ Using fallback polygon: {coords}")
                self.polygon_manager = PolygonManager(coords, settings.DEFAULT_POLYGON_NAME)



async def main():
    """Main entry point"""
    service = DetectionService()
    
    def signal_handler(sig, frame):
        logger.info("⚠ Shutdown signal received")
        service.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await service.initialize()
        await service.run()
    except Exception as e:
        logger.error(f"✗ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
