import webbrowser
import urllib.parse


class Browser:
    def open_google(self):
        webbrowser.open(
            "https://google.com"
        )

    def open_youtube(self):
        webbrowser.open(
            "https://youtube.com"
        )

    def search_google(self, query):
        query = urllib.parse.quote(
            query
        )

        webbrowser.open(
            f"https://www.google.com/search?q={query}"
        )

    def search_youtube(self, query):
        query = urllib.parse.quote(
            query
        )

        webbrowser.open(
            f"https://www.youtube.com/results?search_query={query}"
        )