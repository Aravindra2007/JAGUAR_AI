from ai.image_captioning import (
    ImageCaptioning
)
from ai.object_detection import (
    ObjectDetection
)


class ImageUnderstanding:
    def __init__(self):
        self.captioner = (
            ImageCaptioning()
        )

        self.detector = (
            ObjectDetection()
        )

    def analyze(
        self,
        image_path
    ):
        caption = (
            self.captioner
            .caption(image_path)
        )

        objects = (
            self.detector
            .detect(image_path)
        )

        return {
            "caption":
                caption,

            "objects":
                objects
        }