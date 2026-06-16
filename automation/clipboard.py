import pyperclip


class Clipboard:
    def copy(self, text):
        pyperclip.copy(text)

    def paste(self):
        return pyperclip.paste()