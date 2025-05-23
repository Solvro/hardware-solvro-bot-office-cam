import datetime
import os
from urllib.parse import urljoin

from requests import post

core_url = os.getenv("CORE_URL")


def debounce(func, time=datetime.timedelta(seconds=15)):
    last_call = {"time": datetime.datetime.min}

    def wrapper(*args, **kwargs):
        if datetime.datetime.now() - last_call["time"] >= time:
            last_call["time"] = datetime.datetime.now()
            return func(*args, **kwargs)

    return wrapper


@debounce
def ping(count, image):
    # TODO: finish integrating with core
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
