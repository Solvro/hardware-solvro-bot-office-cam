import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from queue import Empty, Queue
from urllib.parse import urljoin

import cv2
import numpy as np
import numpy.typing as npt

try:
    from picamera2 import Picamera2  # pyright: ignore[reportMissingImports]
    from picamera2.encoders import H264Encoder  # pyright: ignore[reportMissingImports]
    from picamera2.outputs import PyavOutput  # pyright: ignore[reportMissingImports]
    from libcamera import Transform  # pyright: ignore[reportMissingImports]
except ModuleNotFoundError:
    pass
from requests import Request, Response, Session

from solvrocam.debounce import debounce
from solvrocam.person_trackers.yolo_bytetracker import (
    DetectionResult,
    PersonTracker,
)
from solvrocam.preview import Output, Preview


def print_response(res: Response) -> str:
    return "HTTP/1.1 {status_code}\n{headers}\n{body}".format(
        status_code=res.status_code,
        headers="\n".join("{}: {}".format(k, v) for k, v in res.headers.items()),
        body=res.text,
    )


class Solvrocam:
    def __init__(
        self,
        preview: Preview,
        tracker: PersonTracker,
        logger: logging.Logger,
    ):
        self._downscaled_size = (864, 480)
        self._core_base = os.getenv("CORE_URL")
        self._core_url = (
            urljoin(self._core_base, "office/camera") if self._core_base else None
        )

        self._preview: Preview = preview
        self._tracker: PersonTracker = tracker
        self._logger: logging.Logger = logger

        self.frame: npt.NDArray[np.uint8]
        self.downscaled_frame: npt.NDArray[np.uint8]
        self.tracking_result: DetectionResult
        self.image: bytes
        self.counts: list[int] = []

        self.picam2: Picamera2 | None = None
        self.running = False

        self.activity_lock = threading.Lock()
        self.last_activity_timestamp = time.time()

        self.rtmp_thread: threading.Thread | None = None
        self.watchdog_thread: threading.Thread | None = None
        self.processing_thread: threading.Thread | None = None
        self.frame_queue: Queue = Queue(maxsize=1)

    def start_camera(self) -> None:
        self._logger.info("Starting camera...")
        self.picam2 = Picamera2()

        main_size = (4608, 2592)
        main_format = "RGB888"
        # This resolution MUST be at most 1920x1080 or else the encoder fails
        lores_size = (1920, 1080)
        # lores stream MUST be YUV420
        lores_format = "YUV420"
        framerate = 30
        video_config = self.picam2.create_video_configuration(
            main={"size": main_size, "format": main_format},
            lores={"size": lores_size, "format": lores_format},
            display=None,
            transform=Transform(hflip=True, vflip=True),
            encode="lores",
            buffer_count=5,
            controls={"FrameRate": framerate},
        )

        self.picam2.configure(video_config)
        self.picam2.start()
        self._logger.info("Camera hardware started.")

        self.running = True

        # Start all threads
        self.rtmp_thread = threading.Thread(
            target=self._rtmp_connection_thread, daemon=True
        )
        self.rtmp_thread.start()

        self.watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self.watchdog_thread.start()

        self.processing_thread = threading.Thread(
            target=self._processing_loop, daemon=True
        )
        self.processing_thread.start()

        self._logger.info("All threads started.")

    def stop_camera(self) -> None:
        self._logger.info("Stopping camera...")
        self.running = False
        self._preview.output = Output.OFF

        if self.rtmp_thread and self.rtmp_thread.is_alive():
            self.rtmp_thread.join()
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join()

        if self.picam2:
            if self.picam2.encoders:
                self.picam2.stop_recording()
            self.picam2.stop()
        self._logger.info("Camera system stopped.")

    def _rtmp_connection_thread(self) -> None:
        rtmp_server = os.getenv("RTMP_SERVER")
        if not rtmp_server:
            self._logger.warning("RTMP_SERVER not set, streaming thread will exit.")
            return

        encoder = H264Encoder(repeat=True)
        output = PyavOutput(rtmp_server, format="flv")

        while self.running:
            if self.picam2 and not self.picam2.encoders:
                try:
                    self._logger.info(f"Attempting to start stream to {rtmp_server}...")
                    self.picam2.start_recording(encoder, output)
                    self._logger.info("SUCCESS: Background stream started.")
                except Exception as e:
                    self._logger.error(
                        f"Failed to start recording: {e}. Retrying in 1 minute..."
                    )
            # Wait for retry, but check for stop signal
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1)

    def _restart_camera(self) -> None:
        self._logger.warning("Restarting camera")
        self.stop_camera()
        sys.exit(1)

    def _watchdog(self, timeout: int = 15) -> None:
        """Monitors the processing thread and restarts the camera if it becomes unresponsive."""
        while self.running:
            with self.activity_lock:
                last_activity = self.last_activity_timestamp
            if time.time() - last_activity > timeout:
                self._logger.warning(
                    f"Watchdog: No activity for {timeout} seconds. Triggering restart."
                )
                self._restart_camera()
                return
            time.sleep(5)

    def signal_activity(self) -> None:
        """Signals that the processing thread is active."""
        with self.activity_lock:
            self.last_activity_timestamp = time.time()

    def capture_and_queue(self, array_name: str) -> None:
        if not self.picam2:
            return
        try:
            # capture async so that if the camera crashes the thread doesn't hang waiting
            # async allows to wait with a timeout
            job = self.picam2.capture_array(array_name, wait=False)
            frame = self.picam2.wait(job, timeout=0.3)

            if not self.frame_queue.full():
                self.frame_queue.put(frame)
        except Exception as e:
            self._logger.error(f"Failed to capture frame: {e}")

    def _processing_loop(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1)
            except Empty:
                continue
            self.signal_activity()  # Signal that the thread is alive
            self.process_frame(frame)
            self.show()
            self.ping()

    def show(self):
        match self._preview.output:
            case Output.OFF:
                pass
            case Output.CAPTURED:
                self._preview.show(self.frame)
            case Output.DOWNSCALED:
                self._preview.show(self.downscaled_frame)
            case Output.ANNOTATED:
                self._preview.show(np.array(self.tracking_result.processed_frame))

    def process_frame(self, frame: npt.NDArray[np.uint8]):
        self.frame = frame
        self._downscale_frame()
        self._run_detection()
        self.counts.append(
            len(self.tracking_result.ids) if self.tracking_result.ids is not None else 0
        )
        self._logger.debug(f"People detected: {self.counts[-1]}")

    @property
    def preview_output(self) -> Output:
        return self._preview.output

    @preview_output.setter
    def preview_output(self, output: Output):
        self._preview.output = output

    def _encode_image(self):
        self.image = BytesIO(cv2.imencode(".jpeg", self.frame)[1].tobytes()).getvalue()

    @debounce().time(timedelta(seconds=15))
    def ping(self):
        if self._core_url is not None:
            count = 0

            # This removes false negatives where there would be detections between pings, but the frame that is sent doesn't have any.
            # it also improves count accuracy
            detections = np.array([num for num in self.counts if num != 0])
            if detections.size > 0:
                count = int(np.median(detections))
            # Once the ping is called, we clear this
            self.counts.clear()

            timestamp = datetime.now(timezone.utc).isoformat(sep=" ")
            data = {
                "timestamp": timestamp,
                "count": count,
            }
            with Session() as session:
                req = Request("POST", url=self._core_url, data=data)
                if count > 0:
                    self._encode_image()
                    req.files = {
                        "file": (
                            "image.jpeg",
                            self.image,
                            "image/jpeg",
                        )
                    }
                prepped = session.prepare_request(req)

                content = data
                content.update({"file": count > 0})
                self._logger.info(f"Pinging core:\n{content}\n")
                try:
                    res = session.send(prepped)
                    self._logger.debug(print_response(res))
                except Exception as e:
                    self._logger.error(f"Failed to ping core: {e}")
        else:
            self._logger.error(
                "CORE_URL environment variable is not set. Cannot ping core."
            )

    def _downscale_frame(self):
        self.downscaled_frame = cv2.resize(
            self.frame,
            self._downscaled_size,
            interpolation=cv2.INTER_AREA,
        ).astype(np.uint8)

    def _run_detection(self):
        self.tracking_result = self._tracker.track_person(self.downscaled_frame)
