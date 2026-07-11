import time
import pyautogui


class DesktopAgent:

    def click(self):
        pyautogui.click()
        return "Kliknięto."

    def double_click(self):
        pyautogui.doubleClick()
        return "Wykonano dwuklik."

    def right_click(self):
        pyautogui.rightClick()
        return "Kliknięto prawym przyciskiem."

    def move_mouse(self, x: int, y: int, duration: float = 0.2):
        pyautogui.moveTo(x, y, duration=duration)
        return f"Przesunięto mysz na {x}, {y}."

    def type_text(self, text: str):
        pyautogui.write(text, interval=0.02)
        return f"Wpisano: {text}"

    def press(self, key: str):
        pyautogui.press(key)
        return f"Naciśnięto: {key}"

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)
        return f"Wykonano skrót: {' + '.join(keys)}"

    def scroll_down(self, amount: int = 5):
        pyautogui.scroll(-abs(amount))
        return "Przewinięto w dół."

    def scroll_up(self, amount: int = 5):
        pyautogui.scroll(abs(amount))
        return "Przewinięto w górę."

    def copy(self):
        pyautogui.hotkey("ctrl", "c")
        return "Skopiowano."

    def paste(self):
        pyautogui.hotkey("ctrl", "v")
        return "Wklejono."

    def cut(self):
        pyautogui.hotkey("ctrl", "x")
        return "Wycięto."

    def select_all(self):
        pyautogui.hotkey("ctrl", "a")
        return "Zaznaczono wszystko."

    def close_window(self):
        pyautogui.hotkey("alt", "f4")
        return "Zamknięto aktywne okno."

    def switch_window(self):
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.2)
        return "Przełączono okno."

    def minimize_window(self):
        pyautogui.hotkey("win", "down")
        return "Zminimalizowano okno."

    def maximize_window(self):
        pyautogui.hotkey("win", "up")
        return "Zmaksymalizowano okno."

    def open_start_menu(self):
        pyautogui.press("win")
        return "Otworzono menu Start."