import datetime


class debounce:
    def __init__(self):
        pass

    def time(self, time: datetime.timedelta):
        self._time = time
        self._last_call = datetime.datetime.min

        def decorate(func):
            def wrapper(*args, **kwargs):
                if datetime.datetime.now() - self._last_call >= self._time:
                    self._last_call = datetime.datetime.now()
                    return func(*args, **kwargs)

            return wrapper

        return decorate

    def count(self, count: int):
        self._count = count
        self._call_count = 0

        def decorate(func):
            def wrapper(*args, **kwargs):
                self._call_count += 1
                if self._call_count >= self._count:
                    self._call_count = 0
                    return func(*args, **kwargs)

            return wrapper

        return decorate
