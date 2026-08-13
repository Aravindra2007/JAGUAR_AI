
import webbrowser
import os
import subprocess
try:
    import pyautogui
    GUI_AVAILABLE = True
except:
    GUI_AVAILABLE = False
import pywhatkit
import time
from datetime import datetime
from urllib.parse import quote
import re
import webbrowser


class Commands:

    # ----------------------
    # Browser
    # ----------------------
    def open_google(self, text):
        webbrowser.open("https://google.com")
        return "Opening Google."

    def open_youtube(self, text):
        webbrowser.open("https://youtube.com")
        return "Opening YouTube."

    def close_tab(self, text):
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "w")
        return "Closing current tab."

    def close(self, text):
        time.sleep(0.3)
        pyautogui.hotkey("alt", "f4")
        return "Closing application."

    # ----------------------
    # Search
    # ----------------------
    def search_google(self, text):
        query = text.replace("search", "", 1).strip()

        if not query:
            return "What should I search on Google?"

        webbrowser.open(
            f"https://www.google.com/search?q={quote(query)}"
        )

        return f"Searching Google for {query}"

    def search_youtube(self, text):
        query = (
            text.replace("search youtube", "", 1)
                .replace("for", "", 1)
                .strip()
        )

        if not query:
            return "What should I search on YouTube?"

        webbrowser.open(
            f"https://www.youtube.com/results?search_query={quote(query)}"
        )

        return f"Searching YouTube for {query}"

    # ----------------------
    # Play Media
    # ----------------------
    def play_youtube(self, text):
        query = (
            text.replace("play", "", 1)
                .replace("on youtube", "")
                .strip()
        )

        if not query:
            return "What should I play?"

        pywhatkit.playonyt(query)
        return f"Playing {query} on YouTube."

    ## Spotify
    def open_spotify(self, text):
            query = (
                text.replace("search spotify", "", 1)
                    .replace("for", "", 1)
                    .strip()
            )
    
            if not query:
                return "What should I search on spotify?"
    
            webbrowser.open(
                f"https://open.spotify.com/search/={quote(query)}"
            )
    
            return f"Searching Spotify for {query}"

    def play_spotify(self, text):
            query = (
                text.replace("play", "", 1)
                    .replace("on spotify", "")
                    .strip()
            )
    
            if not query:
                return "What should I play?"
    
            pywhatkit.playonyt(query)
            return f"Playing {query} on Spotify."

    
    def book_movie(self, text):
        query = text.replace("movie", "").replace("ticket", "").strip()

        if not query:
            webbrowser.open("https://in.bookmyshow.com/")
            return "Opening BookMyShow."

        url = f"https://in.bookmyshow.com/search?q={quote(query)}"
        webbrowser.open(url)

        return f"Searching movies for {query}"

    def book_bus(self, text):
        text = text.lower()

        match = re.search(r"from (.*?) to (.*?)( on|$)", text)

        if match:
            source = match.group(1).strip()
            destination = match.group(2).strip()
        else:
            return "Say: bus from <city> to <city>"

        url = f"https://www.redbus.in/bus-tickets/{quote(source)}-to-{quote(destination)}"
        webbrowser.open(url)

        return f"Searching buses from {source} to {destination}"


    def book_ttd(self, text):
        webbrowser.open("https://tirupatibalaji.ap.gov.in/")
        return "Opening TTD booking portal."
    # ----------------------
    # IRCTC (Entry Point)
    # ----------------------
    def open_irctc(self, text):
        text = text.lower()
        # --- Extract FROM and TO ---
        match = re.search(r"from (.*?) to (.*?)( on|$)", text)
        if match:
            source = match.group(1).strip()
            destination = match.group(2).strip()
        else:
            return "Please say: from <city> to <city>"

        # --- Extract DATE ---
        date_match = re.search(r"on (.*)", text)

        if date_match:
            date = date_match.group(1).strip()
        else:
            date = ""

        # --- Build Google fallback search (IRCTC doesn't allow direct URL params easily) ---
        query = f"train from {source} to {destination} {date}"

        # url = f"https://www.google.com/search?q={quote(query)}"
        url = f"https://www.makemytrip.com/railways/{quote(source)}-{quote(destination)}-train-tickets.html"
        # url = f"https://www.makemytrip.com/railways/listing?isSeo=true&classCode=&date={quote(date)}&destCity={quote(destination)}&srcCity={quote(source)}&trainNumber="
        

        webbrowser.open(url)

        return f"Searching trains from {source} to {destination} on {date}"

    

    # Gmail
    def open_gmail(self,text):
        webbrowser.open("https://www.gmail.com")
        return "Opeining Gmail"

    # ----------------------
    # Websites
    # ----------------------
    def open_chatgpt(self, text):
        webbrowser.open("https://chat.openai.com")
        return "Opening ChatGPT."

    def open_github(self, text):
        webbrowser.open("https://github.com")
        return "Opening GitHub."

    # ----------------------
    # Applications
    # ----------------------
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
        try:
            subprocess.Popen("code")
            return "Opening VS Code."
        except Exception:
            return "VS Code not found in PATH."

    # ----------------------
    # System Info
    # ----------------------
    def get_time(self, text):
        return datetime.now().strftime("The time is %I:%M %p")

    def get_date(self, text):
        return datetime.now().strftime("Today is %d %B %Y")

    # ----------------------
    # System Control
    # ----------------------
    def shutdown(self, text):
        os.system("shutdown /s /t 5")
        return "Shutting down computer in 5 seconds."

    def restart(self, text):
        os.system("shutdown /r /t 5")
        return "Restarting computer in 5 seconds."

    # ----------------------
    # Exit
    # ----------------------
    def exit(self, text):
        return "exit"
