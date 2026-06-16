import datetime
import sys


class CommandRouter:
    def __init__(self, assistant):
        self.assistant = assistant

        self.commands = {
            # Basic
            "time": self.time,
            "date": self.date,
            "exit": self.exit,
            "quit": self.exit,
            "goodbye": self.exit,

            # Applications
            "open": self.open_app,
            "launch": self.open_app,
            "close": self.close_app,

            # Browser
            "google": self.google,
            "search": self.google,

            # Screenshot AI
            "screenshot": self.screenshot,
            "explain my screen": self.explain_screen,

            # System Monitor
            "cpu": self.cpu_usage,
            "ram": self.ram_usage,
            "battery": self.battery,

            # System Control
            "shutdown": self.shutdown,
            "restart": self.restart,
            "sleep": self.sleep,

            # Memory
            "remember": self.remember,
            "history": self.history,

            # PDF
            "summarize pdf": self.summarize_pdf,

            # Image AI
            "analyze image": self.analyze_image,
        }

    def execute(self, command):
        command = command.lower().strip()

        for key, func in self.commands.items():
            if key in command:
                return func(command)

        # AI fallback
        answer = self.assistant.ask_ai(command)
        self.assistant.speak(answer)

    # ==================================================
    # BASIC
    # ==================================================

    def time(self, command):
        now = datetime.datetime.now()
        self.assistant.speak(
            f"The time is {now.strftime('%I:%M %p')}"
        )

    def date(self, command):
        today = datetime.date.today()
        self.assistant.speak(
            today.strftime("%d %B %Y")
        )

    def exit(self, command):
        self.assistant.speak(
            "Goodbye. Shutting down Jaguar."
        )
        sys.exit()

    # ==================================================
    # APPLICATIONS
    # ==================================================

    def open_app(self, command):
        app = (
            command
            .replace("open", "")
            .replace("launch", "")
            .strip()
        )

        success = (
            self.assistant
            .app_manager
            .open_app(app)
        )

        if success:
            self.assistant.speak(
                f"Opening {app}"
            )
        else:
            self.assistant.speak(
                f"I could not find {app}"
            )

    def close_app(self, command):
        app = (
            command
            .replace("close", "")
            .strip()
        )

        success = (
            self.assistant
            .app_manager
            .close_app(app)
        )

        if success:
            self.assistant.speak(
                f"Closed {app}"
            )
        else:
            self.assistant.speak(
                f"{app} is not running."
            )

    # ==================================================
    # BROWSER
    # ==================================================

    def google(self, command):
        query = (
            command
            .replace("search", "")
            .replace("google", "")
            .strip()
        )

        self.assistant.browser.search_google(
            query
        )

        self.assistant.speak(
            f"Searching Google for {query}"
        )

    # ==================================================
    # SCREEN AI
    # ==================================================

    def screenshot(self, command):
        path = (
            self.assistant
            .vision
            .screen
            .capture()
        )

        self.assistant.speak(
            f"Screenshot saved to {path}"
        )

    def explain_screen(self, command):
        answer = (
            self.assistant
            .vision
            .explain_screen(
                self.assistant
            )
        )

        self.assistant.speak(answer)

    # ==================================================
    # SYSTEM MONITOR
    # ==================================================

    def cpu_usage(self, command):
        cpu = (
            self.assistant
            .cpu_monitor
            .usage()
        )

        self.assistant.speak(
            f"CPU usage is {cpu} percent."
        )

    def ram_usage(self, command):
        ram = (
            self.assistant
            .ram_monitor
            .usage()
        )

        self.assistant.speak(
            f"RAM usage is {ram} percent."
        )

    def battery(self, command):
        battery = (
            self.assistant
            .battery_monitor
            .percentage()
        )

        if battery == -1:
            self.assistant.speak(
                "Battery information is unavailable."
            )
        else:
            self.assistant.speak(
                f"Battery is at {battery} percent."
            )

    # ==================================================
    # SYSTEM CONTROL
    # ==================================================

    def shutdown(self, command):
        self.assistant.speak(
            "Shutting down the computer."
        )

        self.assistant.system.shutdown()

    def restart(self, command):
        self.assistant.speak(
            "Restarting the computer."
        )

        self.assistant.system.restart()

    def sleep(self, command):
        self.assistant.speak(
            "Putting the computer to sleep."
        )

        self.assistant.system.sleep()

    # ==================================================
    # MEMORY
    # ==================================================

    def remember(self, command):
        text = (
            command
            .replace("remember", "")
            .strip()
        )

        self.assistant.memory.save(
            "user_memory",
            text
        )

        self.assistant.speak(
            "I will remember that."
        )

    def history(self, command):
        messages = (
            self.assistant
            .memory
            .last_messages(5)
        )

        if not messages:
            self.assistant.speak(
                "No history found."
            )
            return

        response = ""

        for msg in messages:
            response += (
                f"{msg['role']}: "
                f"{msg['content']}\n"
            )

        print(response)
        self.assistant.speak(
            "Showing the last five messages."
        )

    # ==================================================
    # PDF
    # ==================================================

    def summarize_pdf(self, command):
        self.assistant.speak(
            "Please select a PDF file."
        )

        # TODO:
        # integrate QFileDialog here

    # ==================================================
    # IMAGE AI
    # ==================================================

    def analyze_image(self, command):
        self.assistant.speak(
            "Please select an image."
        )

        # TODO:
        # integrate QFileDialog here