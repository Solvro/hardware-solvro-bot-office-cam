import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DetectionResult:
    boxes: np.ndarray
    ids: np.ndarray | None = None
    confidences: np.ndarray | None = None
    processed_frame: np.ndarray| None = None


class PersonTracker(ABC):
    @abstractmethod
    def __init__(self, detection_model: str, tracking_method: str) -> None:
        pass

    @abstractmethod
    def track_person(self, frame: np.ndarray) -> DetectionResult:
        pass
