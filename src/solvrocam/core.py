import datetime
import logging
import os
from urllib.parse import urljoin

import cv2
import numpy as np
from requests import post, Response

core_url = os.getenv("CORE_URL")


def debounce(func, time=datetime.timedelta(seconds=15)):
    last_call = {"time": datetime.datetime.min}

    def wrapper(*args, **kwargs):
        if datetime.datetime.now() - last_call["time"] >= time:
            last_call["time"] = datetime.datetime.now()
            return func(*args, **kwargs)

    return wrapper


def print_response(res: Response) -> str:
    return "HTTP/1.1 {status_code}\n{headers}\n\n{body}".format(
        status_code=res.status_code,
        headers="\n".join("{}: {}".format(k, v) for k, v in res.headers.items()),
        body=res.content,
    )


@debounce
def ping(count: int, image: np.ndarray, logger: logging.Logger):
    if core_url is not None:
        try:
            if count > 0:
                logger.info(
                    print_response(
                        post(
                            urljoin(core_url, "office/camera"),
                            data={
                                "timestamp": datetime.datetime.now(
                                    datetime.timezone.utc
                                ).isoformat(sep=" "),
                                "count": count,
                            },
                            files={
                                "file": (
                                    "image.png",
                                    cv2.imencode(".png", image)[1].tobytes(),
                                    "image/png",
                                )
                            },
                        )
                    )
                )
            else:
                logger.info(
                    print_response(
                        post(
                            urljoin(core_url, "office/camera"),
                            json={
                                "timestamp": datetime.datetime.now(
                                    datetime.timezone.utc
                                ).isoformat(sep=" "),
                                "count": count,
                            },
                        )
                    )
                )
        except Exception as e:
            logger.error(f"Failed to ping core: {e}")
