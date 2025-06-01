import typer
import logging
import cv2
import os
from solvrocam.processing import process_frame
from solvrocam.person_trackers.yolo_bytetracker import YOLOByteTracker


def debug(
    file_path: str = typer.Argument(..., help="Path to image or video file to process"),
):
    logger = logging.getLogger(__name__)
    tracker = YOLOByteTracker()

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise typer.Exit(code=1)

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        frame = cv2.imread(file_path)
        if frame is None:
            logger.error(f"Failed to read image: {file_path}")
            raise typer.Exit(code=1)
        res = process_frame(frame, tracker)
        cv2.imshow("Debug - Annotated", res.processed_frame)  # pyright: ignore
        cv2.waitKey(10000)
        cv2.destroyAllWindows()
    else:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {file_path}")
            raise typer.Exit(code=1)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            res = process_frame(frame, tracker)
            cv2.imshow("Debug - Annotated", res.processed_frame)  # pyright: ignore
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cap.release()
        cv2.destroyAllWindows()
