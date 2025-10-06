import numpy as np
from shapely.geometry import Point, Polygon

class PolygonManager:
    def __init__(self, coordinates=None, area_name="default"):
        """
        Initialize polygon manager
        
        Args:
            coordinates: list of [x, y] points
            area_name: Name of the area
        """
        self.coordinates = coordinates or []
        self.area_name = area_name
        self.polygon = None
        self.previous_states = {}  # {track_id: was_inside}

        if self.coordinates and len(self.coordinates) >= 3:
            self.update_polygon(self.coordinates)

    def update_polygon(self, coordinates, frame_size=None, original_size=None):
        """
        Update polygon coordinates and optionally rescale to match resized frame.
        
        Args:
            coordinates: list of [x, y] points
            frame_size: (width, height) of YOLO frame (resized)
            original_size: (width, height) of original video stream
        """
        # Handle coordinate scaling (important!)
        if frame_size and original_size:
            fw, fh = frame_size
            ow, oh = original_size
            if ow > 0 and oh > 0:
                scale_x = fw / ow
                scale_y = fh / oh
                scaled_coords = [[x * scale_x, y * scale_y] for x, y in coordinates]
                self.coordinates = scaled_coords
            else:
                self.coordinates = coordinates
        else:
            self.coordinates = coordinates

        # Update shapely polygon
        if len(self.coordinates) >= 3:
            self.polygon = Polygon(self.coordinates)

        self.clear_states()

    def is_point_inside(self, x, y):
        """Check if a single point is inside polygon"""
        if self.polygon is None or len(self.coordinates) < 3:
            return False
        point = Point(x, y)
        return self.polygon.contains(point)

    def is_bbox_inside(self, bbox):
        """
        Check if bounding box center is inside polygon
        
        Args:
            bbox: [x1, y1, x2, y2]
            
        Returns:
            bool
        """
        if len(bbox) < 4:
            return False
        
        x1, y1, x2, y2 = bbox[:4]
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        return self.is_point_inside(cx, cy)

    def check_entry_exit(self, track_id, current_inside):
        """
        Check if object entered or exited polygon
        
        Args:
            track_id: object tracking ID
            current_inside: bool, is object currently inside
            
        Returns:
            str: "entry", "exit", or None
        """
        event = None
        if track_id in self.previous_states:
            previous_inside = self.previous_states[track_id]
            if not previous_inside and current_inside:
                event = "entry"
            elif previous_inside and not current_inside:
                event = "exit"

        # Update state
        self.previous_states[track_id] = current_inside
        return event

    def clear_states(self):
        """Clear previous tracking states"""
        self.previous_states = {}

    def get_coordinates(self):
        """Return polygon coordinates (list of [x, y])"""
        return self.coordinates


# -------------------------
# Global instance for runtime use
# -------------------------
POLYGON_MANAGER = PolygonManager()
