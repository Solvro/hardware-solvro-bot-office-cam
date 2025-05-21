import cv2
import torch
import numpy as np
from ultralytics import YOLO
from pathlib import Path

from solvro_cam.person_trackers.person_tracker import PersonTracker, DetectionResult


class YOLOByteTracker(PersonTracker):
    def __init__(self, 
                 detection_model: str | None = None,
                 tracking_method: str | None = None) -> None:
        if not detection_model:
            detection_model = str((Path(__file__).parent / "models" / "yolo11n_ncnn_model").resolve())
        if not tracking_method:
            tracking_method = str((Path(__file__).parent / "models" / "bytetrack.yaml").resolve())

        self.model = YOLO(detection_model, task="detect")
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
        
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = self._to_numpy(results[0].boxes.xyxy).astype(int)
            confidences = self._to_numpy(results[0].boxes.conf) if hasattr(results[0].boxes, "conf") else np.ones(len(boxes))
            
            if results[0].boxes.id is not None:
                ids = self._to_numpy(results[0].boxes.id).astype(int)
        
        annotated_frame = self.annotate_frame(frame, boxes, ids)
        
        return DetectionResult(
            boxes=boxes,
            ids=ids,
            confidences=confidences,
            processed_frame=annotated_frame
        )
    
    def _to_numpy(self, array: np.ndarray | torch.Tensor) -> np.ndarray:
        if isinstance(array, torch.Tensor):
            return array.cpu().numpy()
        return np.asarray(array)

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
