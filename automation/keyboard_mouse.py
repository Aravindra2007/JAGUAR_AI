import pyautogui


class KeyboardMouse:
    def type(self, text):
        pyautogui.write(text)

    def press(self, key):
        pyautogui.press(key)

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)

    def click(self, x, y):
        pyautogui.click(x, y)