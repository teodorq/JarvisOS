import webbrowser
import pyautogui
import time
from urllib.parse import quote_plus


class BrowserAgent:
    def open_url(self, url: str) -> str:
        webbrowser.open(url)
        return f"Otwieram adres: {url}"

    def open_google(self) -> str:
        webbrowser.open("https://google.com")
        return "Otwieram Google."

    def open_youtube(self) -> str:
        webbrowser.open("https://youtube.com")
        return "Otwieram YouTube."

    def google_search(self, query: str) -> str:
        encoded_query = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}"
        webbrowser.open(url)
        return f"Szukam w Google: {query}"

    def youtube_search(self, query: str) -> str:
        encoded_query = quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
        webbrowser.open(url)
        return f"Szukam na YouTube: {query}"

    def type_in_browser(self, text: str) -> str:
        time.sleep(1)
        pyautogui.write(text, interval=0.03)
        return f"Wpisuję w przeglądarce: {text}"

    def press_enter(self) -> str:
        pyautogui.press("enter")
        return "Naciskam Enter."