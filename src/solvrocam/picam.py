from picamera2 import Picamera2  # pyright: ignore[reportMissingImports]

main_size = (4608, 2592)
main_format = "RGB888"
framerate = 10


def setup_camera() -> Picamera2:
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(
        main={"size": main_size, "format": main_format},
        display=None,
        buffer_count=5,
        controls={"FrameRate": framerate},
    )

    picam2.configure(video_config)
    picam2.start()
    return picam2
