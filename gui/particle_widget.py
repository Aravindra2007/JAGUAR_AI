from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import QTimer
import random


class Particle:

    def __init__(self,w,h):

        self.x=random.randint(0,w)

        self.y=random.randint(0,h)

        self.dx=random.uniform(-1.5,1.5)

        self.dy=random.uniform(-1.5,1.5)

        self.size=random.randint(2,5)


class ParticleWidget(QWidget):

    def __init__(self):

        super().__init__()

        self.particles=[Particle(1920,1080) for _ in range(180)]

        self.timer=QTimer()

        self.timer.timeout.connect(self.animate)

        self.timer.start(16)

    def animate(self):

        w=self.width()

        h=self.height()

        for p in self.particles:

            p.x+=p.dx

            p.y+=p.dy

            if p.x<0 or p.x>w:

                p.dx*=-1

            if p.y<0 or p.y>h:

                p.dy*=-1

        self.update()

    def paintEvent(self,event):

        painter=QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for p in self.particles:

            painter.setPen(QColor(0,191,255))

            painter.setBrush(QColor(0,191,255))

            painter.drawEllipse(int(p.x),int(p.y),p.size,p.size)