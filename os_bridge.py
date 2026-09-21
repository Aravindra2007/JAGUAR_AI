import threading
import time
from queue import Queue
from os_tools import JaguarOSController
from PyQt6.QtWidgets import QApplication

class OSBridge:
    """
    The Bridge connects the Voice/Flask backend to the PyQt6 GUI.
    Since the GUI runs in its own main thread, the Bridge uses a Queue
    to send commands from the backend to the UI.
    """
    def __init__(self, gui_window=None):
        self.queue = Queue()
        self.os_controller = JaguarOSController()
        self.gui_window = gui_window

    def send_command(self, text):
        """Called by app.py or router.py when a voice command is detected."""
        print(f"[Bridge] Received command: {text}")
        self.queue.put(text)

        # Also execute the tool immediately via the controller
        # (This ensures the action happens even if GUI is minimized)
        result = self.process_text_to_tool(text)
        return result

    def process_text_to_tool(self, text):
        """
        Simple logic to map natural language to OS tools.
        In a full version, this is where the LLM (Tool Use) would live.
        """
        text = text.lower()
        if "open notepad" in text:
            return self.os_controller.open_app("notepad")
        elif "open d drive" in text:
            return self.os_controller.manage_file("create_folder", "D:/Jaguar_Auto") # Example
        elif "write" in text and "notepad" in text:
            return self.os_controller.manage_file("write_file", "D:/note.txt", "Voice written text")
        elif "lock" in text:
            return self.os_controller.system_control("lock")

        return "Command recognized but no OS tool mapped."

    def log_event(self, event):
        print(f"[Bridge Log] {event}")

    def check_queue(self):
        """The GUI calls this periodically to update the status bar."""
        if not self.queue.empty():
            return self.queue.get()
        return None

def start_gui_with_bridge():
    """Launcher to start the GUI and the Bridge together."""
    app = QApplication(sys.argv)
    from control_gui import JaguarControlCenter

    bridge = OSBridge()
    window = JaguarControlCenter(bridge=bridge)

    # Add a timer to the window to check the bridge queue
    timer = QTimer()
    def poll_bridge():
        cmd = bridge.check_queue()
        if cmd:
            window.update_status_bar(f"Voice Command: {cmd}")

    timer.timeout.connect(poll_bridge)
    timer.start(500) # Poll every 0.5 seconds

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    import sys
    from PyQt6.QtCore import QTimer
    start_gui_with_bridge()
