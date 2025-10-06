import numpy as np
from scipy.spatial import distance as dist
from collections import OrderedDict, defaultdict
import cv2


class ObjectTracker:
    def __init__(self, max_disappeared=30):
        """
        Simple centroid-based object tracker
        """
        self.next_object_id = 0
        self.objects = OrderedDict()  # {object_id: centroid}
        self.disappeared = OrderedDict()
        self.max_disappeared = max_disappeared
        self.track_history = defaultdict(list)

    def register(self, centroid):
        """Register new object"""
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.track_history[self.next_object_id] = [centroid]
        self.next_object_id += 1

    def deregister(self, object_id):
        """Deregister lost object"""
        del self.objects[object_id]
        del self.disappeared[object_id]
        if object_id in self.track_history:
            del self.track_history[object_id]

    def update(self, detections):
        """Update tracker with new detections"""
        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        input_centroids = np.zeros((len(detections), 2), dtype="int")
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det[:4]
            cx = int((x1 + x2) / 2.0)
            cy = int((y1 + y2) / 2.0)
            input_centroids[i] = (cx, cy)

        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())
            D = dist.cdist(np.array(object_centroids), input_centroids)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue
                if D[row, col] < 100:
                    object_id = object_ids[row]
                    self.objects[object_id] = input_centroids[col]
                    self.disappeared[object_id] = 0
                    self.track_history[object_id].append(input_centroids[col])
                    if len(self.track_history[object_id]) > 30:
                        self.track_history[object_id] = self.track_history[object_id][-30:]
                    used_rows.add(row)
                    used_cols.add(col)

            unused_rows = set(range(D.shape[0])) - used_rows
            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            unused_cols = set(range(D.shape[1])) - used_cols
            for col in unused_cols:
                self.register(input_centroids[col])

        return self.objects

    def get_tracks_with_boxes(self, detections):
        """Return list of [x1, y1, x2, y2, conf, track_id]"""
        if len(detections) == 0:
            return []
        tracked_objects = self.update(detections)
        tracks_with_boxes = []
        for det in detections:
            x1, y1, x2, y2, conf = det[:5]
            cx = int((x1 + x2) / 2.0)
            cy = int((y1 + y2) / 2.0)
            min_dist = float('inf')
            matched_id = None
            for obj_id, obj_centroid in tracked_objects.items():
                d = np.linalg.norm(np.array([cx, cy]) - np.array(obj_centroid))
                if d < min_dist and d < 50:
                    min_dist = d
                    matched_id = obj_id
            if matched_id is not None:
                tracks_with_boxes.append([x1, y1, x2, y2, conf, matched_id])
        return tracks_with_boxes

    def draw_tracks(self, frame, tracked_detections, polygon_manager=None):
        """Draw tracking lines and bounding boxes on the frame"""
        for det in tracked_detections:
            x1, y1, x2, y2, conf, track_id = det
            color = (0, 0, 255)
            if polygon_manager and polygon_manager.is_bbox_inside([x1, y1, x2, y2]):
                color = (0, 255, 0)

            # bbox + ID
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"ID {track_id}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # trajectory line
            if track_id in self.track_history:
                pts = self.track_history[track_id]
                for i in range(1, len(pts)):
                    if pts[i - 1] is None or pts[i] is None:
                        continue
                    cv2.line(frame, pts[i - 1], pts[i], color, 2)

        return frame
