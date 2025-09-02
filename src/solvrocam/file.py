import logging
import os

import cv2
import numpy as np
import typer
from typing_extensions import Annotated

from solvrocam.logs import setup_logging
from solvrocam.preview import CV2Preview, Output

app = typer.Typer()


@app.command()
def file(
    file_path: Annotated[
        str,
        typer.Argument(
            exists=True,
            file_okay=True,
            readable=True,
            help="Path to image or video file to process",
        ),
    ],
    output: Annotated[
        Output,
        typer.Option(
            "--output",
            "-o",
            case_sensitive=False,
            help="Processing stage for the preview to output",
        ),
    ] = Output.ANNOTATED,
):
    logger = logging.getLogger(__name__)
    setup_logging(logger)

    # lazy import to improve cli responsiveness, these imports take 1s
    from solvrocam.detection import Solvrocam
    from solvrocam.person_trackers.yolo_bytetracker import YOLOByteTracker
    solvrocam = Solvrocam(CV2Preview(logger), YOLOByteTracker(), logger)
    solvrocam.preview_output = output

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        frame = cv2.imread(file_path)
        if frame is None:
            logger.error(f"Failed to read image: {file_path}")
            raise typer.Exit(code=1)

        solvrocam.process_frame(frame.astype(np.uint8))
        while solvrocam.preview_output != Output.OFF:
            solvrocam.show()

    else:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {file_path}")
            raise typer.Exit(code=1)

        while solvrocam.preview_output != Output.OFF:
            ret, frame = cap.read()
            if not ret:
                break
            solvrocam.process_frame(frame.astype(np.uint8))
            solvrocam.show()
        cap.release()


if __name__ == "__main__":
    app()
