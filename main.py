from core.assistant import JaguarAssistant
import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)

    assistant = JaguarAssistant()

    window = MainWindow(assistant)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()