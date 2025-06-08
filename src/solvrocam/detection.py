import logging
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urljoin

import cv2
import numpy as np
import numpy.typing as npt
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
        self, preview: Preview, tracker: PersonTracker, logger: logging.Logger
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
                    self._logger.info(print_response(res))
                except Exception as e:
                    self._logger.error(f"Failed to ping core: {e}")
        else:
            self._logger.error(
                "CORE_URL environment variable is not set. Cannot ping core."
            )

    def _downscale_frame(self):
        self.downscaled_frame = cv2.resize(
            self.frame, self._downscaled_size, interpolation=cv2.INTER_AREA
        ).astype(np.uint8)

    def _run_detection(self):
        self.tracking_result = self._tracker.track_person(self.downscaled_frame)


# TODO: socket listener for preview output changes
