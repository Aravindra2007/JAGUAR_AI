class ReminderManager:
    def __init__(self):
        self.reminders = []

    def add(
        self,
        text,
        callback
    ):
        self.reminders.append(
            (text, callback)
        )