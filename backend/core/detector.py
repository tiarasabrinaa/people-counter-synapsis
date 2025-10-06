from ultralytics import YOLO
import cv2
import numpy as np


class YOLODetector:
    def __init__(self, model_path, conf_threshold=0.5, iou_threshold=0.45):
        """
        Initialize YOLO detector
        
        Args:
            model_path: Path to YOLO model file
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS
        """
        try:
            self.model = YOLO(model_path)
            print(f"✓ YOLO model loaded: {model_path}")
        except Exception as e:
            print(f"✗ Error loading YOLO model: {e}")
            raise
        
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
    
    def detect(self, frame):
        """
        Detect people in frame
        
        Args:
            frame: Input image (BGR format)
            
        Returns:
            list of detections [[x1, y1, x2, y2, conf], ...]
        """
        try:
            # Run inference
            results = self.model(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False
            )
            
            detections = []
            
            if len(results) > 0:
                result = results[0]
                
                # Extract boxes
                if result.boxes is not None and len(result.boxes) > 0:
                    boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                    confidences = result.boxes.conf.cpu().numpy()
                    classes = result.boxes.cls.cpu().numpy()
                    
                    # Filter for person class (usually class 0)
                    for i, cls in enumerate(classes):
                        if cls == 0:  # person class
                            box = boxes[i]
                            conf = confidences[i]
                            detections.append([
                                int(box[0]), int(box[1]), 
                                int(box[2]), int(box[3]), 
                                float(conf)
                            ])
            
            return detections
            
        except Exception as e:
            print(f"Error in detection: {e}")
            return []