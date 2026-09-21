import os
import subprocess
import shutil
import ctypes
import pyautogui
import psutil
from pathlib import Path

class JaguarOSController:
    """Handles the actual execution of OS-level commands."""

    def __init__(self):
        self.home_dir = Path.home()

    def open_app(self, app_name):
        try:
            # Try to open using the start command (handles most Windows apps)
            subprocess.Popen(f"start {app_name}", shell=True)
            return f"Successfully opened {app_name}."
        except Exception as e:
            return f"Could not open {app_name}: {e}"

    def manage_file(self, action, path, content=""):
        """Full control over files: create, delete, write."""
        try:
            p = Path(path)
            if action == "create_folder":
                p.mkdir(parents=True, exist_ok=True)
                return f"Folder created at {path}"

            elif action == "write_file":
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"File written to {path}"

            elif action == "delete":
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return f"Deleted {path}"

            return "Invalid action specified."
        except Exception as e:
            return f"File error: {e}"

    def system_control(self, command):
        """High-level system commands."""
        if command == "lock":
            ctypes.windll.user32.LockWorkStation()
            return "PC Locked."
        elif command == "restart":
            os.system("shutdown /r /t 1")
            return "Restarting..."
        elif command == "shutdown":
            os.system("shutdown /s /t 1")
            return "Shutting down..."
        return "Unknown system command."

    def get_system_stats(self):
        """Returns real-time CPU and RAM usage."""
        return {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent
        }
