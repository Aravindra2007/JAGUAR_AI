import os
import shutil


class FileManager:
    def create_folder(self, path):
        os.makedirs(
            path,
            exist_ok=True
        )

    def delete(self, path):
        if os.path.isfile(path):
            os.remove(path)

        elif os.path.isdir(path):
            shutil.rmtree(path)

    def move(self, src, dst):
        shutil.move(src, dst)

    def copy(self, src, dst):
        shutil.copy(src, dst)