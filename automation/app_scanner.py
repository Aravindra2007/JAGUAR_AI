import os
import json
from pathlib import Path


class AppScanner:
    def __init__(self):
        self.apps = {}

    def scan(self):
        start_menus = [
            Path(os.environ["PROGRAMDATA"]) /
            "Microsoft/Windows/Start Menu/Programs",

            Path(os.environ["APPDATA"]) /
            "Microsoft/Windows/Start Menu/Programs"
        ]

        for menu in start_menus:
            if not menu.exists():
                continue

            for file in menu.rglob("*.lnk"):
                name = file.stem.lower()
                self.apps[name] = str(file)

        return self.apps

    def save(self):
        Path("memory").mkdir(exist_ok=True)

        with open(
            "memory/apps.json",
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                self.apps,
                f,
                indent=4
            )