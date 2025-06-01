import cv2


def process_frame(frame, tracker):
    downscaled_size = (576, 320)
    downscaled_frame = cv2.resize(frame, downscaled_size, interpolation=cv2.INTER_AREA)

    result = tracker.track_person(downscaled_frame)
    return result
