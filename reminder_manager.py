import json
import os
import time
import threading
from datetime import datetime
from speaker import speak
import state
import overlay

class ReminderManager:
    def __init__(self, reminders_path="reminders.json"):
        self.reminders_path = reminders_path
        # Ensure the path is absolute if relative
        if not os.path.isabs(self.reminders_path):
            self.reminders_path = os.path.join(os.path.dirname(__file__), self.reminders_path)

        self.running = True

    def check_reminders(self):
        """Polls the reminders file and triggers alerts for due reminders."""
        while self.running:
            try:
                if os.path.exists(self.reminders_path):
                    with open(self.reminders_path, "r", encoding="utf-8") as f:
                        reminders = json.load(f)

                    if not isinstance(reminders, list):
                        reminders = []

                    now = datetime.now()
                    triggered = []
                    remaining = []

                    for r in reminders:
                        fire_at = datetime.fromisoformat(r["fire_at_iso"])
                        if now >= fire_at:
                            triggered.append(r)
                        else:
                            remaining.append(r)

                    if triggered:
                        # Save the remaining reminders back to file
                        with open(self.reminders_path, "w", encoding="utf-8") as f:
                            json.dump(remaining, f, indent=2)

                        # Trigger the reminders
                        for r in triggered:
                            msg = r.get("message", "Reminder!")
                            state.set_status("Reminder Alert!")
                            speak(f"Reminder: {msg}", language=state.get_language())
                            # We update the overlay through state.set_status

                # Check every 30 seconds to avoid high CPU usage
                time.sleep(30)
            except Exception as e:
                print(f"[ReminderManager] Error: {e}")
                time.sleep(60)

    def start(self):
        """Launch the reminder checker in a background thread."""
        t = threading.Thread(target=self.check_reminders, daemon=True)
        t.start()
        print("[ReminderManager] Monitoring reminders...")

    def stop(self):
        self.running = False

# Singleton instance
reminder_manager = ReminderManager()

def start_reminder_service():
    reminder_manager.start()
