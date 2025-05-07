import cv2
import numpy as np
from ultralytics import YOLO

from person_trackers.person_tracker import PersonTracker, DetectionResult


class YOLOByteTracker(PersonTracker):
    def __init__(self, 
                 detection_model: str = "models/yolo11n_ncnn_model", 
                 tracking_method: str = "person_trackers/bytetrack.yaml") -> None:
        self.model = YOLO(detection_model)
        self.tracking_config = tracking_method
        self.person_class_id = 0
        
    def track_person(self, frame: np.ndarray) -> DetectionResult:
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=self.tracking_config,
            classes=[self.person_class_id]
        )
        
        boxes = np.empty((0, 4), dtype=int)
        ids = np.empty(0, dtype=int)
        confidences = np.empty(0, dtype=float)
        
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            confidences = results[0].boxes.conf.cpu().numpy() if hasattr(results[0].boxes, "conf") else np.ones(len(boxes))
            
            if results[0].boxes.id is not None:
                ids = results[0].boxes.id.cpu().numpy().astype(int)
        
        annotated_frame = self.annotate_frame(frame, boxes, ids)
        
        return DetectionResult(
            boxes=boxes,
            ids=ids,
            confidences=confidences,
            processed_frame=annotated_frame
        )
    
    def annotate_frame(self, frame: np.ndarray, boxes: np.ndarray, ids: np.ndarray) -> np.ndarray:
        annotated_frame = frame.copy()
        
        for box, person_id in zip(boxes, ids):
            cv2.rectangle(annotated_frame, (box[0], box[1]), (box[2], box[3]), (255, 0, 255), 2)
            cv2.putText(
                annotated_frame, 
                f"{person_id}", 
                (box[0], box[1] - 10), 
                cv2.FONT_HERSHEY_COMPLEX, 
                0.9, 
                (255, 0, 255), 
                2
            )
            
        return annotated_frame
