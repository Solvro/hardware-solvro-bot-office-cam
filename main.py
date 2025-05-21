import datetime
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from urllib.parse import urljoin

import cv2
from dotenv import load_dotenv
from picamera2 import Picamera2  # pyright: ignore[reportMissingImports]
from requests import post
from systemd.journal import JournalHandler  # pyright: ignore[reportMissingImports]

from person_trackers.yolo_bytetracker import YOLOByteTracker

# TODO: break this file up into smaller modules

# Configure logging
logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.DEBUG)

if not os.path.isdir("/home/solvrocam/hardware-solvro-bot-office-cam/logs"):
    os.mkdir("/home/solvrocam/hardware-solvro-bot-office-cam/logs")

file_handler = TimedRotatingFileHandler(
    "/home/solvrocam/hardware-solvro-bot-office-cam/logs/log",
    when="D",
    backupCount=7,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

journal_handler = JournalHandler()
journal_handler.setLevel(logging.INFO)
journal_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
logger.addHandler(journal_handler)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


def debounce(func, time=datetime.timedelta(seconds=15)):
    last_call = {"time": datetime.datetime.min}

    def wrapper(*args, **kwargs):
        if datetime.datetime.now() - last_call["time"] >= time:
            last_call["time"] = datetime.datetime.now()
            return func(*args, **kwargs)

    return wrapper


load_dotenv()
core_url = os.getenv("CORE_URL")


@debounce
def ping(count, image):
    if core_url is not None:
        if count > 0:
            post(
                urljoin(core_url, "office/camera"),
                data={
                    "timestamp": datetime.datetime.now(datetime.timezone.utc),
                    "count": count,
                },
                files={"file": image},
            )
        else:
            post(
                urljoin(core_url, "office/camera"),
                json={
                    "timestamp": datetime.datetime.now(datetime.timezone.utc),
                    "count": count,
                },
            )


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


while True:
    frame = picam2.capture_array("main")
    downscaled_frame = cv2.resize(frame, downscaled_size, interpolation=cv2.INTER_AREA)
    result = tracker.track_person(downscaled_frame)
    count = len(result.ids) if result.ids is not None else 0
    ping(count, frame)

    if count > 0:
        logger.info(f"People detected, count= {count}")
