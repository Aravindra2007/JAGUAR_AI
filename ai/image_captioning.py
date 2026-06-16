from transformers import (
    BlipProcessor,
    BlipForConditionalGeneration
)
from PIL import Image


class ImageCaptioning:
    def __init__(self):
        self.processor = (
            BlipProcessor
            .from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
        )

        self.model = (
            BlipForConditionalGeneration
            .from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
        )

    def caption(
        self,
        image_path
    ):
        image = Image.open(
            image_path
        )

        inputs = (
            self.processor(
                image,
                return_tensors="pt"
            )
        )

        output = self.model.generate(
            **inputs
        )

        return (
            self.processor.decode(
                output[0],
                skip_special_tokens=True
            )
        )