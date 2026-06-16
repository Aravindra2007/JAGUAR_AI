class MultimodalRouter:
    def route(
        self,
        path
    ):
        extension = (
            path
            .split(".")[-1]
            .lower()
        )

        if extension == "pdf":
            return "pdf"

        if extension in [
            "png",
            "jpg",
            "jpeg",
            "webp"
        ]:
            return "image"

        return "unknown"