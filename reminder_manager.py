"""Poll and deliver the signed-in user's Firestore reminders."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from speaker import speak
import state
import db


class ReminderManager:
    def __init__(self):
        self.running = True

    def check_reminders(self):
        while self.running:
            try:
                user_id = state.get_current_user_id()
                if user_id:
                    now = datetime.now(timezone.utc)
                    for reminder in db.list_reminders(
                        str(user_id),
                        pending_only=True,
                    ):
                        fire_at = reminder.get("fire_at")
                        if isinstance(fire_at, str):
                            fire_at = datetime.fromisoformat(fire_at)
                        if fire_at is None:
                            fire_at = datetime.fromisoformat(
                                reminder["fire_at_iso"]
                            )
                        if fire_at.tzinfo is None:
                            fire_at = fire_at.astimezone()
                        if now >= fire_at.astimezone(timezone.utc):
                            if db.mark_reminder_delivered(
                                str(user_id),
                                reminder["id"],
                            ):
                                message = reminder.get("message", "Reminder!")
                                state.set_status("Reminder Alert!")
                                speak(
                                    f"Reminder: {message}",
                                    language=state.get_language(),
                                )
                time.sleep(30)
            except Exception as error:
                print(f"[ReminderManager] Error: {error}")
                time.sleep(60)

    def start(self):
        thread = threading.Thread(target=self.check_reminders, daemon=True)
        thread.start()
        print("[ReminderManager] Monitoring cloud reminders...")

    def stop(self):
        self.running = False


reminder_manager = ReminderManager()


def start_reminder_service():
    reminder_manager.start()
