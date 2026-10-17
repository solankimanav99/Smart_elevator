"""
Object Detection Module - Multi-object YOLO detection with graceful fallback
"""
import cv2
import numpy as np
from collections import Counter

YOLO_AVAILABLE = False
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("[DETECTOR] YOLO loaded successfully")
except Exception as e:
    print(f"[DETECTOR] YOLO not available: {e} — running in Dummy Mode")

# Classes relevant to elevator monitoring
RELEVANT_CLASSES = {
    0: "person", 24: "backpack", 26: "handbag", 28: "suitcase",
    39: "bottle", 41: "cup", 63: "laptop", 67: "cell phone",
    73: "book", 66: "keyboard"
}

class ObjectDetector:
    def __init__(self):
        self.available = YOLO_AVAILABLE
        self.model = None
        self.conf_threshold = 0.25  # Lower threshold for better multi-object detection
        self.iou_threshold = 0.60   # Less aggressive NMS to keep overlapping objects
        if self.available:
            try:
                self.model = YOLO("yolov8n.pt")
                print("[DETECTOR] YOLOv8n model loaded")
            except Exception as e:
                print(f"[DETECTOR] Model load failed: {e}")
                self.available = False

    def detect(self, frame):
        """Run detection on full frame, return annotated frame + results dict."""
        results = {
            "object_count": 0,
            "detected_objects": "",
            "human_detected": False,
            "details": []
        }
        
        if not self.available or self.model is None:
            cv2.putText(frame, "AI: Dummy Mode", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            return frame, results

        try:
            # Full frame inference — no cropping
            detections = self.model.predict(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
                classes=list(RELEVANT_CLASSES.keys())
            )

            object_names = []
            for det in detections:
                boxes = det.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = RELEVANT_CLASSES.get(cls_id, f"class_{cls_id}")
                    object_names.append(label)
                    
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Color coding
                    if label == "person":
                        color = (0, 255, 0)
                        results["human_detected"] = True
                    else:
                        color = (255, 200, 0)
                    
                    # Draw bounding box and label
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    text = f"{label} ({conf:.2f})"
                    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                    cv2.putText(frame, text, (x1 + 2, y1 - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Build summary
            counts = Counter(object_names)
            results["object_count"] = len(object_names)
            results["detected_objects"] = ", ".join(
                [f"{name} x{cnt}" for name, cnt in counts.items()]
            )
            results["details"] = [
                {"name": name, "count": cnt} for name, cnt in counts.items()
            ]

        except Exception as e:
            print(f"[DETECTOR] Detection error: {e}")
            cv2.putText(frame, "Detection Error", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return frame, results
