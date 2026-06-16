from PyQt6.QtWidgets import QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QMovie,QPixmap
from core.voice_thread import VoiceThread

class MainWindow(QMainWindow):
    def __init__(self, assistant):
        super().__init__()

        self.assistant = assistant
        self.setWindowTitle("Jaguar AI Assistant")
        self.setGeometry(200, 200, 400, 300)

        self.label = QLabel("Click Start to begin listening")
        self.image_label = QLabel()

        pixmap = QPixmap("Jaguar.png")  # <-- your image path
        self.image_label.setPixmap(pixmap)
        self.image_label.setScaledContents(True)
        self.image_label.setFixedSize(200, 200)

        ## this is for gif animation
       

        self.start_btn = QPushButton("Start Voice")
        self.stop_btn = QPushButton("Stop Voice")

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        
        layout.addWidget(self.image_label)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.voice_thread = None

        self.start_btn.clicked.connect(self.start_voice)
        self.stop_btn.clicked.connect(self.stop_voice)

    def start_voice(self):
        self.voice_thread = VoiceThread(self.process_voice)
        self.voice_thread.start()
        self.label.setText("Listening...")

    def stop_voice(self):
        if self.voice_thread:
            self.voice_thread.stop()
        self.label.setText("Stopped")

    def process_voice(self, text):
        result = self.assistant.handle_command(text)
        print("VOICE RECEIVED:", text)
        # result = self.assistant.handle_command(text)
        print("RESULT:", result)

        if result == "exit":
            self.close()
        elif result == "opened":
            self.label.setText("App opened")
        else:
            self.label.setText("Command not found")