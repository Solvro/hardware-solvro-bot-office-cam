import logging
import sys
from io import BytesIO

import cv2

from solvrocam.core import ping
from solvrocam.logs import setup_logging
from solvrocam.person_trackers.yolo_bytetracker import YOLOByteTracker
from solvrocam.picam import setup_camera
from solvrocam.processing import process_frame

# Configure logging
logger = logging.getLogger(__name__)
setup_logging(logger)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


picam2 = setup_camera()
tracker = YOLOByteTracker()


def detect():
    counts: list[int] = []

    while True:
        frame = picam2.capture_array("main")
        img = BytesIO(cv2.imencode(".jpeg", frame)[1].tobytes())
        result = process_frame(frame, tracker)

        count = len(result.ids) if result.ids is not None else 0
        counts.append(count)
        logger.debug(f"People detected: {count}")

        ping(counts, img.getvalue(), logger)


if __name__ == "__main__":
    detect()
