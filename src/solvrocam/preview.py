import logging
import socket
import struct
from abc import ABC, abstractmethod
from enum import StrEnum, auto, unique
from os import getenv
from pathlib import Path
from queue import Empty, Queue
from threading import Thread, current_thread

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
        self._port = int(getenv("PREVIEW_PORT", "6900"))
        self._stream_port = int(getenv("PREVIEW_STREAM_PORT", "6901"))
        self._socket_thread = Thread(target=self._socket_listener, daemon=True)
        self._socket_thread.start()
        self._frame_queue: Queue = Queue(maxsize=1)
        self._frame_sender_thread: Thread | None = None

    @property
    def output(self) -> Output:
        return self._output

    @output.setter
    def output(self, output: Output):
        if self._output == output:
            return

        previous_thread = self._frame_sender_thread
        self._output = output

        if output == Output.OFF:
            if previous_thread is not None and previous_thread.is_alive():
                # A thread can't join itself.
                if current_thread().ident != previous_thread.ident:
                    previous_thread.join()
        else:
            if (
                self._frame_sender_thread is None
                or not self._frame_sender_thread.is_alive()
            ):
                self._frame_sender_thread = Thread(
                    target=self._frame_sender_worker, daemon=True
                )
                self._frame_sender_thread.start()

    def show(self, frame: cv2.typing.MatLike):
        if self.output != Output.OFF:
            try:
                # Non-blocking put
                self._frame_queue.put_nowait(frame)
            except Exception:
                # Queue is full, drop frame
                pass

    def _frame_sender_worker(self):
        PORT = self._stream_port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", PORT))
            sock.listen()
            self._logger.info(f"Preview stream socket listening on port {PORT}")
            conn, _ = sock.accept()
            with conn:
                self._logger.info("Preview client connected")
                while self.output != Output.OFF:
                    try:
                        frame = self._frame_queue.get(timeout=0.1)
                        # Send frame metadata (shape)
                        shape = frame.shape
                        header = struct.pack(">III", *shape)
                        conn.sendall(header)
                        # Send frame data
                        conn.sendall(frame.tobytes())
                    except Empty:
                        pass  # No new frame
                    except (BrokenPipeError, ConnectionResetError):
                        self._logger.info("Preview client disconnected")
                        break  # client disconnected, wait for new one
        except Exception as e:
            self._logger.error(f"Frame sender error: {e}", exc_info=True)
        finally:
            self.output = Output.OFF
            sock.close()
            self._logger.info("Preview stream socket closed")

    def _socket_listener(self):
        PORT = self._port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", PORT))
            sock.listen()
            self._logger.info(f"Preview command socket listening on port {PORT}")
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


def _set_stage(stage: Output):
    PORT = int(getenv("PREVIEW_PORT", "6900"))

    try:
        with socket.create_connection(("127.0.0.1", PORT)) as sock:
            try:
                sock.sendall(stage.encode("utf-8"))
            except Exception as e:
                typer.echo(f"Error sending stage: {e}", err=True)
                raise typer.Exit(code=1)
    except OSError as e:
        typer.echo(f"Error connecting to preview server: {e}", err=True)
        raise typer.Exit(code=1)


app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    stage: Annotated[
        Output | None,
        typer.Option(
            "--stage",
            "-s",
            case_sensitive=False,
            help="Set the processing stage for the preview to output.",
        ),
    ] = None,
):
    """
    Manage the preview stream.
    """
    if ctx.invoked_subcommand is None:
        if stage:
            _set_stage(stage)
        else:
            typer.echo("Error: Missing option '--stage' / '-s'.", err=True)
            raise typer.Exit(code=1)


def _recv_all(sock, n):
    """Helper function to receive n bytes from a socket."""
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


@app.command()
def start(
    stage: Annotated[
        Output | None,
        typer.Option(
            "--stage",
            "-s",
            case_sensitive=False,
            help="Set the processing stage for the preview to output.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            writable=True,
            help="Save frames to a video file.",
        ),
    ] = None,
):
    """
    Start the preview window.
    """
    if stage:
        _set_stage(stage)

    PORT = int(getenv("PREVIEW_STREAM_PORT", "6901"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    header_size = struct.calcsize(">III")
    video_writer = None

    try:
        sock.connect(("127.0.0.1", PORT))
        typer.echo(f"Connected to preview stream on port {PORT}")
        window_name = "Preview"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while True:
            # Receive header
            header_data = _recv_all(sock, header_size)
            if not header_data:
                break
            shape = struct.unpack(">III", header_data)

            # Receive frame data
            frame_size = shape[0] * shape[1] * shape[2]
            frame_data = _recv_all(sock, frame_size)
            if not frame_data:
                break

            # Reconstruct frame
            frame = np.frombuffer(frame_data, dtype=np.uint8).reshape(shape)

            if output and video_writer is None:
                height, width, _ = frame.shape
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                video_writer = cv2.VideoWriter(
                    str(output), fourcc, 20.0, (width, height)
                )

            if video_writer:
                video_writer.write(frame)

            cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except OSError as e:
        typer.echo(f"Error connecting to preview stream: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"An error occurred: {e}", err=True)
    finally:
        if video_writer:
            video_writer.release()
        _set_stage(Output.OFF)
        cv2.destroyAllWindows()
        sock.close()
        typer.echo("Preview stopped")


if __name__ == "__main__":
    app()
