import tkinter as tk
from threading import Thread
import state

class JaguarOverlay:
    def __init__(self):
        self.root = None
        self.label = None
        self.status_colors = {
            "Idle": "#2c3e50",          # Dark Blue/Grey
            "Listening...": "#27ae60", # Green
            "Processing...": "#e67e22",  # Orange
            "Awaiting confirmation...": "#f1c40f", # Yellow
            "Offline": "#c0392b",       # Red
        }

    def create_overlay(self):
        self.root = tk.Tk()

        # 1. Remove window borders and title bar
        self.root.overrideredirect(True)

        # 2. Keep window always on top
        self.root.attributes("-topmost", True)

        # 3. Make it semi-transparent
        self.root.attributes("-alpha", 0.8)

        # 4. Set size and position (Top right corner)
        screen_width = self.root.winfo_screenwidth()
        width, height = 180, 35
        x = screen_width - width - 20
        y = 50
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # 5. The Label
        self.label = tk.Label(
            self.root,
            text="Jaguar: Idle",
            fg="white",
            bg=self.status_colors["Idle"],
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=5
        )
        self.label.pack(expand=True, fill="both")

        # Make it a rounded-looking pill (simulated by bg)
        # Note: True rounded corners in tkinter require complex canvas work,
        # but a clean rectangle is standard for status bars.

    def update_status(self, status):
        if not self.label:
            return

        color = self.status_colors.get(status, "#2c3e50")
        self.label.config(text=f"Jaguar: {status}", bg=color)

    def run(self):
        # Run the overlay in its own thread so it doesn't block the main app
        self.create_overlay()
        self.root.mainloop()

# Singleton instance
overlay_instance = JaguarOverlay()

def start_overlay():
    # Use a daemon thread so it closes when the main program exits
    t = Thread(target=overlay_instance.run, daemon=True)
    t.start()

def update_overlay(status):
    overlay_instance.update_status(status)
