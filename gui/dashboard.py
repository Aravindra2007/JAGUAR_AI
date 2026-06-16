from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel
)
from PyQt6.QtCore import QTimer

from system.cpu_monitor import CPUMonitor
from system.ram_monitor import RAMMonitor
from system.battery_monitor import BatteryMonitor


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()

        self.cpu = CPUMonitor()
        self.ram = RAMMonitor()
        self.battery = BatteryMonitor()

        self.layout = QVBoxLayout()

        self.cpu_label = QLabel()
        self.ram_label = QLabel()
        self.battery_label = QLabel()

        self.layout.addWidget(
            self.cpu_label
        )

        self.layout.addWidget(
            self.ram_label
        )

        self.layout.addWidget(
            self.battery_label
        )

        self.setLayout(
            self.layout
        )

        self.timer = QTimer()
        self.timer.timeout.connect(
            self.update_data
        )
        self.timer.start(1000)

        self.update_data()

    def update_data(self):
        self.cpu_label.setText(
            f"CPU: {self.cpu.usage()}%"
        )

        self.ram_label.setText(
            f"RAM: {self.ram.usage()}%"
        )

        battery = (
            self.battery
            .percentage()
        )

        if battery != -1:
            self.battery_label.setText(
                f"Battery: {battery}%"
            )
        else:
            self.battery_label.setText(
                "Battery: Not Available"
            )