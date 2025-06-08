import logging
from abc import ABC, abstractmethod
from enum import StrEnum, auto, unique
import os
import socket
from threading import Thread, current_thread
from queue import Queue, Empty

import cv2
import numpy as np
import numpy.typing as npt
import typer
from typing_extensions import Annotated


@unique
class Output(StrEnum):
    OFF = auto()
    CAPTURED = auto()
    DOWNSCALED = auto()
    ANNOTATED = auto()


class Preview(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def show(self, frame: npt.NDArray[np.uint8]):
        pass

    @property
    @abstractmethod
    def output(self) -> Output:
        pass

    @output.setter
    @abstractmethod
    def output(self, output: Output):
        pass


class CV2Preview(Preview):
    def __init__(self, logger: logging.Logger):
        self._output: Output = Output.OFF
        self._logger = logger
        self._port = int(os.getenv("PREVIEW_PORT", "6900"))
        self._socket_thread = Thread(target=self._socket_listener, daemon=True)
        self._socket_thread.start()
        self._frame_queue: Queue = Queue(maxsize=1)
        self._preview_thread: Thread | None = None

    @property
    def output(self) -> Output:
        return self._output

    @output.setter
    def output(self, output: Output):
        if self._output == output:
            return

        previous_thread = self._preview_thread
        self._output = output

        if output == Output.OFF:
            if previous_thread is not None and previous_thread.is_alive():
                # A thread can't join itself.
                if current_thread().ident != previous_thread.ident:
                    previous_thread.join()
        else:
            if self._preview_thread is None or not self._preview_thread.is_alive():
                self._preview_thread = Thread(target=self._preview_worker, daemon=True)
                self._preview_thread.start()

    def show(self, frame: cv2.typing.MatLike):
        if self.output != Output.OFF:
            try:
                # Non-blocking put
                self._frame_queue.put_nowait(frame)
            except Exception:
                # Queue is full, drop frame
                pass

    def _preview_worker(self):
        window_name = "Preview"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        try:
            while self.output != Output.OFF:
                try:
                    frame = self._frame_queue.get(timeout=0.1)
                    cv2.imshow(window_name, frame)
                except Empty:
                    pass  # No new frame

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    # This will trigger the setter and cause the loop to exit
                    self.output = Output.OFF
                    break
        finally:
            cv2.destroyWindow(window_name)

    def _socket_listener(self):
        PORT = self._port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", PORT))
            sock.listen()
            self._logger.info(f"Preview socket listening on port {PORT}")
            while True:
                conn, _ = sock.accept()
                with conn:
                    data = conn.recv(1024)
                    if not data:
                        continue
                    try:
                        new_output = Output(data.decode("utf-8").strip())
                        self.output = new_output
                        self._logger.info(f"Set preview output to {new_output}")
                    except ValueError:
                        self._logger.warning(f"Invalid output value received: {data}")
        except Exception as e:
            self._logger.error(f"Socket listener error: {e}", exc_info=True)
        finally:
            sock.close()


app = typer.Typer()


@app.command()
def preview(
    output: Annotated[
        Output,
        typer.Option(
            "--output",
            "-o",
            prompt=True,
            case_sensitive=False,
            help="Processing stage for the preview to output",
        ),
    ],
):
    PORT = int(os.getenv("PREVIEW_PORT", "6900"))

    try:
        with socket.create_connection(("127.0.0.1", PORT)) as sock:
            try:
                sock.sendall(output.encode("utf-8"))
            except Exception as e:
                typer.echo(f"Error sending output: {e}", err=True)
                raise typer.Exit(code=1)
    except OSError as e:
        typer.echo(f"Error connecting to preview server: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()