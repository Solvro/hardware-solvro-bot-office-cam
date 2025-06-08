import logging
import os
import sys

import typer
from picamera2 import Picamera2  # pyright: ignore[reportMissingImports]
from picamera2.encoders import H264Encoder  # pyright: ignore[reportMissingImports]
from picamera2.outputs import PyavOutput  # pyright: ignore[reportMissingImports]

from solvrocam.detection import Solvrocam
from solvrocam.logs import setup_logging
from solvrocam.person_trackers.yolo_bytetracker import YOLOByteTracker
from solvrocam.preview import CV2Preview  # pyright: ignore[reportMissingImports]


def setup() -> Picamera2:
    picam2 = Picamera2()
    main_size = (4608, 2592)
    main_format = "RGB888"
    lores_size = (2304, 1296)
    lores_format = "RGB888"
    framerate = 30
    video_config = picam2.create_video_configuration(
        main={"size": main_size, "format": main_format},
        lores={"size": lores_size, "format": lores_format},
        display=None,
        encode="lores",
        buffer_count=5,
        controls={"FrameRate": framerate},
    )

    picam2.configure(video_config)
    picam2.start()

    rtmp_server = os.getenv("RTMP_SERVER")
    if rtmp_server is not None:
        encoder = H264Encoder()
        encoder.output = PyavOutput(rtmp_server)
        try:
            picam2.start_encoder(encoder)
        except Exception:
            pass

    return picam2


app = typer.Typer()


@app.command()
def camera():
    logger = logging.getLogger(__name__)
    setup_logging(logger)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception

    solvrocam = Solvrocam(CV2Preview(logger), YOLOByteTracker(), logger)

    picam2 = setup()

    while True:
        frame = picam2.capture_array("main")
        solvrocam.process_frame(frame)
        solvrocam.show()
        solvrocam.ping()


if __name__ == "__main__":
    camera()
