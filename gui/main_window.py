from PyQt6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer

from datetime import datetime
import psutil

from core.voice_thread import VoiceThread
from gui.styles import STYLE


class MainWindow(QMainWindow):

    def __init__(self, assistant):
        super().__init__()

        self.assistant = assistant

        self.setWindowTitle("🐆 Jaguar AI")
        self.resize(1280, 720)
        self.setStyleSheet(STYLE)

        ####################################################
        # Clock
        ####################################################

        self.clock = QLabel()
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ####################################################
        # Status
        ####################################################

        self.label = QLabel("Say 'Hey Jaguar'")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ####################################################
        # Logo
        ####################################################

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap("assets/logo/jaguar.png")

        pixmap = pixmap.scaled(
            1320,
            1320,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(pixmap)

        ####################################################
        # System Information
        ####################################################

        self.cpu_label = QLabel()
        self.cpu_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.ram_label = QLabel()
        self.ram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ####################################################
        # Buttons
        ####################################################

        self.start_btn = QPushButton("🎤 Start Listening")
        self.stop_btn = QPushButton("⏹ Stop Listening")
        self.exit_btn = QPushButton("❌ Exit")

        self.start_btn.setMinimumHeight(50)
        self.stop_btn.setMinimumHeight(50)
        self.exit_btn.setMinimumHeight(50)

        ####################################################
        # Layout
        ####################################################

        layout = QVBoxLayout()

        layout.addWidget(self.clock)

        layout.addStretch()

        layout.addWidget(self.image_label)

        layout.addWidget(self.label)

        layout.addStretch()

        layout.addWidget(self.cpu_label)
        layout.addWidget(self.ram_label)

        layout.addSpacing(15)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.exit_btn)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

        ####################################################
        # Voice Thread
        ####################################################

        self.voice_thread = None

        ####################################################
        # Timers
        ####################################################

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self.update_system_info)
        self.system_timer.start(1000)

        self.update_clock()
        self.update_system_info()

        ####################################################
        # Buttons
        ####################################################

        self.start_btn.clicked.connect(self.start_voice)
        self.stop_btn.clicked.connect(self.stop_voice)
        self.exit_btn.clicked.connect(self.close)

    ####################################################
    # Clock
    ####################################################

    def update_clock(self):

        now = datetime.now()

        self.clock.setText(
            now.strftime("%I:%M:%S %p\n%A, %d %B %Y")
        )

    ####################################################
    # CPU / RAM
    ####################################################

    def update_system_info(self):

        cpu = psutil.cpu_percent()

        ram = psutil.virtual_memory().percent

        self.cpu_label.setText(f"💻 CPU Usage : {cpu}%")

        self.ram_label.setText(f"🧠 RAM Usage : {ram}%")

    ####################################################
    # Start Voice
    ####################################################

    def start_voice(self):

        if self.voice_thread is None or not self.voice_thread.is_alive():

            self.voice_thread = VoiceThread(self.process_voice)

            self.voice_thread.start()

            self.label.setText("🎤 Listening for Wake Word...")

    ####################################################
    # Stop Voice
    ####################################################

    def stop_voice(self):

        if self.voice_thread:

            self.voice_thread.stop()

            self.voice_thread = None

        self.label.setText("🛑 Voice Assistant Stopped")

    ####################################################
    # Process Voice
    ####################################################

    def process_voice(self, text):

        print("VOICE:", text)

        result = self.assistant.handle_command(text)

        print("RESULT:", result)

        if result == "opened":

            self.label.setText(f"✅ {text}")

        elif result == "exit":

            self.close()

        else:

            self.label.setText("❌ Command Not Found")

    ####################################################
    # Close Event
    ####################################################

    def closeEvent(self, event):

        if self.voice_thread:

            self.voice_thread.stop()

        event.accept()