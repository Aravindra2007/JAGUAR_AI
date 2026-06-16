import os
import json
import subprocess
import psutil

from automation.app_scanner import AppScanner


class AppManager:
    def __init__(self):
        self.apps = {}

        try:
            with open(
                "memory/apps.json",
                "r",
                encoding="utf-8"
            ) as f:
                self.apps = json.load(f)

        except:
            scanner = AppScanner()
            self.apps = scanner.scan()
            scanner.save()

    def open_app(self, app_name):
        app_name = app_name.lower()

        for name, path in self.apps.items():
            if app_name in name:
                os.startfile(path)
                return True

        return False

    def close_app(self, app_name):
        app_name = app_name.lower()

        for process in psutil.process_iter(
            ["pid", "name"]
        ):
            try:
                name = (
                    process.info["name"]
                    .lower()
                )

                if app_name in name:
                    process.kill()
                    return True

            except:
                pass

        return False