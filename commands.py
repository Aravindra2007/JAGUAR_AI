import webbrowser
import os
import subprocess
import pyautogui
import pywhatkit
import time
from datetime import datetime
from urllib.parse import quote


class Commands:

    def open_google(self, text):
        webbrowser.open("https://google.com")
        return "Opening Google."

    def open_youtube(self, text):
        webbrowser.open("https://youtube.com")
        return "Opening YouTube."

    def close_tab(self, text):
        time.sleep(0.5) 
        pyautogui.hotkey("ctrl", "w")
        return "Closing current tab."
    
    def close(self,text):
        time.sleep(0.5)
        pyautogui.hotkey("alt","f4")
        return f"{text}"

    def play_youtube(self, text):
        song = (
            text.replace("play", "", 1)
                .replace("on youtube", "")
                .strip()
        )

        pywhatkit.playonyt(song)
        return f"Playing {song} on YouTube."

    def search_youtube(self, text):
        query = (
            text.replace("search youtube", "", 1)
                .replace("for", "", 1)
                .strip()
        )

        webbrowser.open(
            f"https://www.youtube.com/results?search_query={quote(query)}"
        )

        return f"Searching YouTube for {query}"

    def search_google(self, text):
        query = text.replace("search", "", 1).strip()

        webbrowser.open(
            f"https://www.google.com/search?q={quote(query)}"
        )

        return f"Searching Google for {query}"

    def open_chatgpt(self, text):
        webbrowser.open("https://chat.openai.com")
        return "Opening ChatGPT."

    def open_github(self, text):
        webbrowser.open("https://github.com")
        return "Opening GitHub."

    def open_notepad(self, text):
        os.system("start notepad")
        return "Opening Notepad."

    def open_calculator(self, text):
        os.system("start calc")
        return "Opening Calculator."

    def open_paint(self, text):
        os.system("start mspaint")
        return "Opening Paint."

    def open_cmd(self, text):
        os.system("start cmd")
        return "Opening Command Prompt."

    def open_vscode(self, text):
        subprocess.Popen("code")
        return "Opening VS Code."

    def get_time(self, text):
        return datetime.now().strftime("The time is %I:%M %p")

    def get_date(self, text):
        return datetime.now().strftime("Today is %d %B %Y")

    def shutdown(self, text):
        os.system("shutdown /s /t 5")
        return "Shutting down computer."

    def restart(self, text):
        os.system("shutdown /r /t 5")
        return "Restarting computer."

    def exit(self, text):
        return "exit"
