from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation


class BreathingLabel(QLabel):

    def __init__(self):
        super().__init__()

        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)

        self.anim = QPropertyAnimation(effect,b"opacity")

        self.anim.setDuration(1800)

        self.anim.setStartValue(.45)

        self.anim.setEndValue(1)

        self.anim.setLoopCount(-1)

        self.anim.start()