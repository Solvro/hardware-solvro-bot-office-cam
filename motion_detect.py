import logging
import os
import signal
import sys
import time

import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import FileOutput
from systemd import journal

# TODO: more resilient false positive detection
# TODO: test out opencv
# TODO: auto ssh
# TODO: aliases


def remove_fluke_recordings():
    if motion_frames < 10:
        filename = encoder.output().fileoutput()
        os.remove(filename)
        logger.info("Less than 10 motion frames, deleting Recording")


# Shutdown gracefully
def handler(signum, frame):
    logger.info(f"Received signal {signal.strsignal(signum)}, shutting down")
    if encoding:
        picam2.stop_encoder()
        logger.info("Stopping Recording")
        remove_fluke_recordings()
    sys.exit(0)


signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

# Configure logging
logging.basicConfig(
    format="%(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)
logger.addHandler(journal.JournalHandler())

lsize = (320, 240)
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": (1280, 720), "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"},
    display=None,
    buffer_count=90,
    controls={"FrameRate": 30},
)
picam2.configure(video_config)
encoder = H264Encoder()
picam2.start()

w, h = lsize
prev = None
encoding = False
motion_frames = 0
ltime = 0

while True:
    curr = picam2.capture_buffer("lores")
    curr = curr[: w * h].reshape(h, w)
    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(curr, prev)).mean()
        if mse > 1.75:
            if not encoding:
                encoder.output = FileOutput(
                    f"/home/solvrocam/Videos/{time.strftime('%d %m %H:%M:%S', time.localtime())}.h264"
                )
                picam2.start_encoder(encoder, quality=Quality.VERY_HIGH)
                encoding = True
                logger.info(f"Starting Recording, mse={mse}")
            else:
                logger.debug(f"Mid Recording, mse={mse}")
            motion_frames += 1
            ltime = time.time()

        else:
            if encoding and time.time() - ltime > 30.0:
                picam2.stop_encoder()
                encoding = False
                logger.info(f"Stopped Recording, motion_frames={motion_frames}")
                remove_fluke_recordings()
                motion_frames = 0
    prev = curr
