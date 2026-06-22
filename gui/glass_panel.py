from PyQt6.QtWidgets import QFrame


class GlassPanel(QFrame):

    def __init__(self):

        super().__init__()

        self.setStyleSheet("""

        QFrame{

        background:rgba(255,255,255,20);

        border:1px solid rgba(255,255,255,40);

        border-radius:25px;

        }

        """)