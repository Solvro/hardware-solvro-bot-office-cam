import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from person_trackers.yolo_bytetracker import YOLOByteTracker

from picamera2 import Picamera2
from systemd.journal import JournalHandler

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


def ping():
    # TODO: post detection to server
    pass


lsize = (640, 480)
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": lsize, "format": "YUV420"},
    display=None,
    buffer_count=90,
    controls={"FrameRate": 30},
)

picam2.configure(video_config)
picam2.start()
tracker = YOLOByteTracker()

ping_time = 0

while True:
    frame = picam2.capture_array("main")
    result = tracker.track_person(frame)
    count = len(result.ids)

    if count > 0:
        logger.info(f"People detected, count= {count}")
        if time.time() - ping_time > 60 or ping_time == 0:
            ping()
            ping_time = time.time()

    else:
        ping_time = 0
