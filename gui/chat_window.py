from PyQt6.QtWidgets import (
    QWidget,
    QTextEdit,
    QVBoxLayout
)


class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        layout = QVBoxLayout()

        layout.addWidget(
            self.chat
        )

        self.setLayout(layout)

    def add_message(
        self,
        sender,
        message
    ):
        self.chat.append(
            f"<b>{sender}</b>: "
            f"{message}"
        )