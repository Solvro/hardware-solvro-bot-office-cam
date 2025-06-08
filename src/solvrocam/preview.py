import logging
from abc import ABC, abstractmethod
from enum import StrEnum, auto, unique
import os
import socket

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
        self._window: str | None = None
        self._logger = logger

    @property
    def output(self) -> Output:
        return self._output

    @output.setter
    def output(self, output: Output):
        if self._output == Output.OFF and output != Output.OFF:
            self._output = output
            self._start()
        elif self._output != Output.OFF and output == Output.OFF:
            self._output = output
            self._stop()

    def show(self, frame: cv2.typing.MatLike):
        cv2.imshow(f"Debug - {self.output.name}", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            self._output = Output.OFF
            self._stop()

    def _start(self):
        if self._window is None:
            self._window = f"Debug - {self._output.name}"
            cv2.namedWindow(self._window, cv2.WINDOW_NORMAL)
        else:
            self._logger.critical(
                "Attempted to start a preview that was already started."
            )

    def _stop(self):
        if self._window is not None:
            cv2.destroyWindow(self._window)
            self._window = None
        else:
            self._logger.critical("Attempted to stop a preview that was not started.")


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
    try:
        sock = socket.create_connection(
            ("localhost", int(os.getenv("PREVIEW_PORT", "6900")))
        )
    except OSError as e:
        typer.echo(f"Error connecting to preview server: {e}", err=True)
        raise typer.Exit(code=1)

    try:
        sock.sendall(output.encode("utf-8"))
    except Exception as e:
        typer.echo(f"Error sending output: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
