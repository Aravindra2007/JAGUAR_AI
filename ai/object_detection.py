from transformers import pipeline


class ObjectDetection:
    def __init__(self):
        self.detector = pipeline(
            "object-detection"
        )

    def detect(
        self,
        image_path
    ):
        return self.detector(
            image_path
        )