import logging
import sys

import cv2
from dotenv import load_dotenv
from picamera2 import Picamera2  # pyright: ignore[reportMissingImports]

from solvro_cam.logs import setup_logging
from solvro_cam.core import ping
from solvro_cam.person_trackers.yolo_bytetracker import YOLOByteTracker

# TODO: break this file up into smaller modules

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

main_size = (4608, 2592)
downscaled_size = (576, 320)
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": main_size, "format": "YUV420"},
    display=None,
    buffer_count=5,
    controls={"FrameRate": 10},
)

picam2.configure(video_config)
picam2.start()
tracker = YOLOByteTracker()


def main():
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
    main()
