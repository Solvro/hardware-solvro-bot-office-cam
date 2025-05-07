# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "ffmpeg-python",
#     "matplotlib",
#     "numpy",
#     "pygame",
# ]
# ///

import os
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import filedialog

import ffmpeg
import matplotlib
import matplotlib.backends.backend_agg as agg
import matplotlib.pyplot as plt
import numpy as np
import pygame

matplotlib.use("Agg")


def select_files():
    root = tk.Tk()
    root.withdraw()
    video_path = filedialog.askopenfilename(
        title="Select MP4 Video",
        filetypes=[("MP4 files", "*.mp4")],
        initialdir=os.path.abspath(__file__).rsplit("/", 1)[0] + "/out",
    )
    log_path = filedialog.askopenfilename(
        title="Select Log File",
        filetypes=[("Log files", "*")],
        initialdir=os.path.abspath(__file__).rsplit("/", 1)[0] + "/logs",
    )
    return video_path, log_path


def parse_log(log_path, video_path):
    filename = os.path.basename(video_path)
    try:
        day, month, time_str = filename.split()[:3]
        h, m, s = map(int, (time_str.split(".")[0].split(":")))
        start_dt = datetime(1900, int(month), int(day), h, m, s)
    except Exception as e:
        print(f"Log filename must be in 'DD MM HH:MM:SS' format. Error: {str(e)}")
        sys.exit(1)

    mse_data = []
    timestamps = []

    with open(log_path, "r") as f:
        for line in f:
            if "mse=" not in line:
                continue
            try:
                parts = line.strip().split()
                timestamp_str = f"{parts[0]} {parts[1]} {parts[2]}"
                entry_dt = datetime.strptime(timestamp_str, "%b %d %H:%M:%S").replace(
                    year=1900
                )
                mse = float(line.split("mse=")[1].split()[0])
                offset = (entry_dt - start_dt).total_seconds()
                mse_data.append(mse)
                timestamps.append(offset)
            except Exception as e:
                print(f"Error parsing line: {line.strip()} - {str(e)}")

    # Spread MSE values evenly within each second
    spread_times = []
    spread_mse = []
    current_sec = -1
    buffer = []

    for t, mse in sorted(zip(timestamps, mse_data)):
        sec = int(t)
        if sec != current_sec and buffer:
            n = len(buffer)
            for i, (bt, bm) in enumerate(buffer):
                spread_time = current_sec + (i + 0.5) / n
                spread_times.append(spread_time)
                spread_mse.append(bm)
            buffer = []
        buffer.append((t, mse))
        current_sec = sec

    if buffer:
        n = len(buffer)
        for i, (bt, bm) in enumerate(buffer):
            spread_time = current_sec + (i + 0.5) / n
            spread_times.append(spread_time)
            spread_mse.append(bm)

    return np.array(spread_times), np.array(spread_mse)


def get_video_info(video_path):
    probe = ffmpeg.probe(video_path)
    video_stream = next(
        (s for s in probe["streams"] if s["codec_type"] == "video"), None
    )
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    fps = eval(video_stream["avg_frame_rate"])
    duration = float(video_stream["duration"])
    return width, height, fps, duration


class VideoPlayer:
    def __init__(self, video_path, mse_times, mse_values, width, height, fps, duration):
        self.video_path = video_path
        self.mse_times = mse_times
        self.mse_values = mse_values
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = duration
        self.plot_width = 600  # Fixed plot width
        self.screen_width = self.width + self.plot_width
        self.screen_height = self.height + 100  # 100px for controls
        self.frame_size = self.width * self.height * 3

        # Plot surfaces
        self.plot_surface = None
        self.line_surface = None
        self.plot_rect = None
        self.line_rect = None

        # Video playback state
        self.paused = False
        self.current_sec = 0
        self.start_time_sec = 0
        self.frame_idx = 0
        self.process = None

        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Video with MSE Plot")
        self.font = pygame.font.Font(None, 36)
        self.clock = pygame.time.Clock()

        # Initialize plot
        self.create_plot_surfaces()
        self.restart_process()

    def create_plot_surfaces(self):
        """Create static plot background and transparent line surface"""
        # Main plot surface
        fig = plt.figure(figsize=(self.plot_width / 100, self.height / 100), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(self.mse_times, self.mse_values, "b-", linewidth=1)
        ax.set_xlabel("Time (s)", color="white")
        ax.set_ylabel("MSE", color="white")
        ax.tick_params(colors="white")
        ax.set_facecolor((0.1, 0.1, 0.1))
        ax.set_xlim(0, self.duration)
        if len(self.mse_values):
            ax.set_ylim(np.min(self.mse_values), np.max(self.mse_values))
        fig.patch.set_facecolor((0.1, 0.1, 0.1))

        canvas = agg.FigureCanvasAgg(fig)
        canvas.draw()
        self.plot_surface = pygame.image.fromstring(
            canvas.tostring_argb(), canvas.get_width_height(), "ARGB"
        )
        self.plot_rect = self.plot_surface.get_rect(topleft=(self.width, 0))
        plt.close(fig)

        # Transparent line surface
        fig = plt.figure(figsize=(self.plot_width / 100, self.height / 100), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_axis_off()
        fig.patch.set_alpha(0)  # Fully transparent
        self.vline = ax.axvline(0, color="red", linewidth=1)
        ax.set_xlim(0, self.duration)
        ax.set_ylim(0, 1)  # Dummy limits

        canvas = agg.FigureCanvasAgg(fig)
        canvas.draw()
        self.line_surface = pygame.image.fromstring(
            canvas.tostring_argb(), canvas.get_width_height(), "ARGB"
        )
        self.line_rect = self.line_surface.get_rect(topleft=(self.width, 0))
        plt.close(fig)

    def update_line_position(self, current_time):
        """Update vertical line position using matplotlib"""
        fig = plt.figure(figsize=(self.plot_width / 100, self.height / 100), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_axis_off()
        fig.patch.set_alpha(0)
        self.vline = ax.axvline(current_time, color="red", linewidth=1)
        ax.set_xlim(0, self.duration)
        ax.set_ylim(0, 1)

        canvas = agg.FigureCanvasAgg(fig)
        canvas.draw()
        self.line_surface = pygame.image.fromstring(
            canvas.tostring_argb(), canvas.get_width_height(), "ARGB"
        )
        plt.close(fig)

    def restart_process(self, start_time=0):
        if self.process:
            self.process.terminate()
        cmd = (
            ffmpeg.input(self.video_path, ss=start_time)
            .output("pipe:", format="rawvideo", pix_fmt="rgb24")
            .compile()
        )
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10**8)
        self.frame_idx = 0

    def draw_controls(self):
        # Play/Pause button
        btn_size = 40
        btn_x = (self.width - btn_size) // 2
        btn_y = self.height + 20
        btn_rect = pygame.Rect(btn_x, btn_y, btn_size, btn_size)
        pygame.draw.rect(self.screen, (50, 50, 50), btn_rect)
        if self.paused:
            pygame.draw.polygon(
                self.screen,
                (255, 255, 255),
                [
                    (btn_x + 13, btn_y + 10),
                    (btn_x + 13, btn_y + 30),
                    (btn_x + 30, btn_y + 20),
                ],
            )
        else:
            pygame.draw.rect(
                self.screen, (255, 255, 255), (btn_x + 12, btn_y + 10, 5, 20)
            )
            pygame.draw.rect(
                self.screen, (255, 255, 255), (btn_x + 23, btn_y + 10, 5, 20)
            )

        # Timeline
        timeline_y = self.height + 60
        timeline_rect = pygame.Rect(10, timeline_y, self.width - 20, 20)
        pygame.draw.rect(self.screen, (70, 70, 70), timeline_rect)
        progress_width = (self.current_sec / self.duration) * (self.width - 20)
        pygame.draw.rect(self.screen, (0, 200, 0), (10, timeline_y, progress_width, 20))

    def handle_click(self, pos):
        btn_rect = pygame.Rect((self.width - 40) // 2, self.height + 20, 40, 40)
        if btn_rect.collidepoint(pos):
            self.paused = not self.paused
            return True

        timeline_rect = pygame.Rect(10, self.height + 60, self.width - 20, 20)
        if timeline_rect.collidepoint(pos):
            seek_x = pos[0] - 10
            seek_time = (seek_x / (self.width - 20)) * self.duration
            self.start_time_sec = seek_time
            self.restart_process(seek_time)
            self.paused = False
            return True
        return False

    def run(self):
        running = True
        while running:
            if not self.paused:
                raw_frame = self.process.stdout.read(self.frame_size)
                if not raw_frame:
                    break

                frame = pygame.image.frombuffer(
                    raw_frame, (self.width, self.height), "RGB"
                )
                self.screen.blit(frame, (0, 0))

                self.current_sec = self.start_time_sec + (self.frame_idx / self.fps)
                self.frame_idx += 1

            # Update plot line
            self.update_line_position(self.current_sec)

            # Draw elements
            self.screen.blit(self.plot_surface, self.plot_rect)
            self.screen.blit(self.line_surface, self.line_rect)
            self.draw_controls()

            # MSE display
            idx = (
                np.abs(self.mse_times - self.current_sec).argmin()
                if len(self.mse_times) > 0
                else -1
            )
            mse_value = (
                self.mse_values[idx]
                if idx != -1 and abs(self.mse_times[idx] - self.current_sec) < 1
                else None
            )
            text = (
                f"Time: {self.current_sec:.1f}s | MSE: {mse_value:.2f}"
                if mse_value
                else f"Time: {self.current_sec:.1f}s | MSE: N/A"
            )
            text_surface = self.font.render(text, True, (255, 255, 255), (0, 0, 0))
            self.screen.blit(text_surface, (10, 10))

            pygame.display.flip()
            self.clock.tick(self.fps if not self.paused else 60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    self.paused = not self.paused

        self.process.terminate()
        pygame.quit()


def play_video(video_path, mse_times, mse_values):
    width, height, fps, duration = get_video_info(video_path)
    player = VideoPlayer(
        video_path, mse_times, mse_values, width, height, fps, duration
    )
    player.run()


if __name__ == "__main__":
    video_path, log_path = select_files()
    if not video_path or not log_path:
        print("No file selected. Exiting.")
        sys.exit(0)
    mse_times, mse_values = parse_log(log_path, video_path)
    play_video(video_path, mse_times, mse_values)
