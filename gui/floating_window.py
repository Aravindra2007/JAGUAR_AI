from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt


class FloatingWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "JAGUAR"
        )

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.resize(
            300,
            150
        )