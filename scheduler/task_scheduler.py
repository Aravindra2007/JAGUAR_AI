import schedule
import time
import threading


class TaskScheduler:
    def __init__(self):
        self.jobs = []

    def every_day(
        self,
        at,
        func
    ):
        schedule.every().day.at(
            at
        ).do(func)

    def run(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    def start(self):
        thread = threading.Thread(
            target=self.run,
            daemon=True
        )

        thread.start()