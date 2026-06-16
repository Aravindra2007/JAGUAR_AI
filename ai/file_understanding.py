import os


class FileUnderstanding:
    def analyze(
        self,
        path
    ):
        return {
            "name":
                os.path.basename(path),

            "size":
                os.path.getsize(path),

            "extension":
                os.path.splitext(path)[1]
        }