import logging
import sys

import typer

from solvrocam.logs import setup_logging
from solvrocam.preview import CV2Preview  # pyright: ignore[reportMissingImports]


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

    # lazy import to improve cli responsiveness, these imports take 1s
    from solvrocam.person_trackers.yolo_bytetracker import YOLOByteTracker
    from solvrocam.detection import Solvrocam
    solvrocam = Solvrocam(CV2Preview(logger), YOLOByteTracker(), logger)
    solvrocam.start_camera()

    try:
        while True:
            solvrocam.capture_and_queue("main")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        solvrocam.stop_camera()


if __name__ == "__main__":
    camera()
