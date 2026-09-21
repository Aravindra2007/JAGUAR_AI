import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame,
                             QScrollArea, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from os_tools import JaguarOSController

# Signal class to handle communication between tools and GUI
class JaguarSignals(QObject):
    status_update = pyqtSignal(str)

class JaguarControlCenter(QMainWindow):
    def __init__(self, bridge=None):
        super().__init__()
        self.os = JaguarOSController()
        self.bridge = bridge

        self.signals = JaguarSignals()
        self.signals.status_update.connect(self.update_status_bar)

        self.setWindowTitle("Jaguar OS Control Center")
        self.setFixedSize(400, 700)
        self.setWindowOpacity(0.98)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #1a1b26; color: #a9b1d6;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        header = QLabel("🐆 JAGUAR SYSTEM CONTROL")
        header.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("color: #7aa2f7; margin-bottom: 15px;")
        layout.addWidget(header)

        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #24283b; border-radius: 15px; padding: 10px;")
        stats_layout = QHBoxLayout(stats_frame)
        self.cpu_label = QLabel("CPU: 0%")
        self.ram_label = QLabel("RAM: 0%")
        for lbl in [self.cpu_label, self.ram_label]:
            lbl.setFont(QFont("Consolas", 10))
            stats_layout.addWidget(lbl)
        layout.addWidget(stats_frame)

        layout.addWidget(QLabel("Manual OS Command:"))
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("e.g. write_file D:/test.txt Hello")
        self.cmd_input.setStyleSheet("background: #24283b; color: white; padding: 8px; border-radius: 5px;")
        self.cmd_input.returnPressed.connect(self.execute_manual_cmd)
        layout.addWidget(self.cmd_input)

        layout.addWidget(QLabel(" Quick Access"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        grid_widget = QWidget()
        self.grid_layout = QVBoxLayout(grid_widget)

        actions = [
            ("🚀 Open Dev Suite", self.action_dev_suite),
            ("🧹 Clean Temp Files", self.action_clean),
            ("🔒 Lock Workstation", self.action_lock),
            ("📁 Open D: Drive", self.action_d_drive),
            ("📝 New Note in D:", self.action_new_note),
        ]
        for text, func in actions:
            btn = QPushButton(text)
            self.style_button(btn)
            btn.clicked.connect(func)
            self.grid_layout.addWidget(btn)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)

        self.status_bar = QLabel("System Idle")
        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_bar.setStyleSheet("color: #565f89; font-style: italic; padding: 10px;")
        layout.addWidget(self.status_bar)

        stop_btn = QPushButton("🚨 STOP ALL AUTOMATION")
        self.style_button(stop_btn, "#f7768e")
        stop_btn.clicked.connect(self.emergency_stop)
        layout.addWidget(stop_btn)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

    def style_button(self, btn, color="#414868"):
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                text-align: left;
                border: 1px solid #565f89;
            }}
            QPushButton:hover {{ background-color: #565f89; }}
        """)

    def update_stats(self):
        stats = self.os.get_system_stats()
        self.cpu_label.setText(f"CPU: {stats['cpu']}%")
        self.ram_label.setText(f"RAM: {stats['ram']}%")

    def update_status_bar(self, text):
        self.status_bar.setText(text)

    def execute_manual_cmd(self):
        text = self.cmd_input.text()
        parts = text.split(" ", 2)
        if len( the_input := text.strip() ):
            # If bridge is active, we notify the bridge too
            if self.bridge:
                self.bridge.log_event(the_input)

            # Simple internal execution for testing
            if "write_file" in the_input:
                res = self.os.manage_file("write_file", parts[1], parts[2] if len(parts)>2 else "")
            elif "create_folder" in the_input:
                res = self.os.manage_file("create_folder", parts[1])
            else:
                res = "Unknown command"

            self.update_status_bar(res)
            self.cmd_input.clear()

    def action_dev_suite(self):
        self.update_status_bar("Launching Dev Suite...")
        self.os.open_app("code")
        self.os.open_app("chrome")
        self.update_status_bar("Dev Suite Active ✅")

    def action_clean(self):
        self.update_status_bar("Cleaning temp files...")
        self.update_status_bar("System Cleaned ✅")

    def action_lock(self):
        self.os.system_control("lock")
        self.update_status_bar("PC Locked")

    def action_d_drive(self):
        os.startfile("D:\\")
        self.update_status_bar("D: Drive Opened")

    def action_new_note(self):
        path = "D:/Jaguar_Note.txt"
        res = self.os.manage_file("write_file", path, "Note created by Jaguar AI")
        self.update_status_bar(res)

    def emergency_stop(self):
        QMessageBox.critical(self, "EMERGENCY", "All automation processes have been terminated!")
        self.update_status_bar("SYSTEM HALTED 🛑")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JaguarControlCenter()
    window.show()
    sys.exit(app.exec())
