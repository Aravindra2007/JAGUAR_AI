from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import QTimer


class VoiceRing(QWidget):

    def __init__(self):
        super().__init__()

        self.radius = 130
        self.growing = True
        self.listening = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def setListening(self, value):
        self.listening = value

    def animate(self):

        if not self.listening:
            return

        if self.growing:
            self.radius += 1
            if self.radius >= 145:
                self.growing = False
        else:
            self.radius -= 1
            if self.radius <= 130:
                self.growing = True

        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(0,191,255))
        pen.setWidth(5)

        painter.setPen(pen)

        center_x = self.width()//2
        center_y = self.height()//2

        painter.drawEllipse(
            center_x-self.radius,
            center_y-self.radius,
            self.radius*2,
            self.radius*2
        )