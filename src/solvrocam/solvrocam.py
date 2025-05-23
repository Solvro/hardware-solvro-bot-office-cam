import logging
import sys

import cv2
from dotenv import load_dotenv

from solvrocam.logs import setup_logging
from solvrocam.core import ping
from solvrocam.picam import setup_camera
from solvrocam.person_trackers.yolo_bytetracker import YOLOByteTracker


# Configure logging
logger = logging.getLogger(__name__)
setup_logging(logger)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


load_dotenv()

picam2 = setup_camera()
downscaled_size = (576, 320)
tracker = YOLOByteTracker()


def solvrocam():
    while True:
        frame = picam2.capture_array("main")
        downscaled_frame = cv2.resize(
            frame, downscaled_size, interpolation=cv2.INTER_AREA
        )
        result = tracker.track_person(downscaled_frame)
        count = len(result.ids) if result.ids is not None else 0
        ping(count, frame)

        if count > 0:
            logger.info(f"People detected, count= {count}")


if __name__ == "__main__":
    solvrocam()
