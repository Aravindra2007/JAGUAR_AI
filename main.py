import threading
import time
import webbrowser

from app import app

# -----------------------------
# NOTE:
# app.py already owns the voice listener (a VoiceListener thread
# started when the module loads). This file's only job is to launch
# the Flask server and open the browser. There is no second
# microphone loop here anymore - running two listeners against the
# same sr.Microphone() at once was the original bug.
# -----------------------------


# -----------------------------
# Open Browser
# -----------------------------
def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


# -----------------------------
# Run Flask
# -----------------------------
def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":

    # Start Flask (this also brings the voice listener thread up,
    # since it's created inside app.py)
    threading.Thread(target=run_flask, daemon=True).start()

    # Open Browser
    threading.Thread(target=open_browser, daemon=True).start()

    # Keep the main thread alive
    while True:
        time.sleep(1)
