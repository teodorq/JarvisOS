from __future__ import annotations

import os
import time
import webbrowser
from urllib.parse import quote_plus

import pyautogui


class BrowserAgent:

    def open_url(
        self,
        url: str,
    ) -> str:

        normalized_url = str(
            url
        ).strip()

        if not normalized_url:
            return "Brak adresu do otwarcia."

        opened = self._open_windows_url(
            normalized_url
        )

        if opened:
            return (
                f"Otwieram adres: "
                f"{normalized_url}"
            )

        return (
            "Nie udało się otworzyć adresu: "
            f"{normalized_url}"
        )

    def open_google(
        self,
    ) -> str:

        url = "https://www.google.com"

        if self._open_windows_url(url):
            return "Otwieram Google."

        return (
            "Nie udało się otworzyć Google."
        )

    def open_youtube(
        self,
    ) -> str:

        url = "https://www.youtube.com"

        if self._open_windows_url(url):
            return "Otwieram YouTube."

        return (
            "Nie udało się otworzyć YouTube."
        )

    def google_search(
        self,
        query: str,
    ) -> str:

        normalized_query = str(
            query
        ).strip()

        if not normalized_query:
            return (
                "Brak tekstu do wyszukania "
                "w Google."
            )

        encoded_query = quote_plus(
            normalized_query
        )

        url = (
            "https://www.google.com/search"
            f"?q={encoded_query}"
        )

        if self._open_windows_url(url):
            return (
                "Szukam w Google: "
                f"{normalized_query}"
            )

        return (
            "Nie udało się uruchomić "
            "wyszukiwania Google."
        )

    def youtube_search(
        self,
        query: str,
    ) -> str:

        normalized_query = str(
            query
        ).strip()

        if not normalized_query:
            return (
                "Brak tekstu do wyszukania "
                "na YouTube."
            )

        encoded_query = quote_plus(
            normalized_query
        )

        url = (
            "https://www.youtube.com/results"
            f"?search_query={encoded_query}"
        )

        if self._open_windows_url(url):
            return (
                "Szukam na YouTube: "
                f"{normalized_query}"
            )

        return (
            "Nie udało się uruchomić "
            "wyszukiwania YouTube."
        )

    def type_in_browser(
        self,
        text: str,
    ) -> str:

        normalized_text = str(
            text
        )

        time.sleep(1)

        pyautogui.write(
            normalized_text,
            interval=0.03,
        )

        return (
            "Wpisuję w przeglądarce: "
            f"{normalized_text}"
        )

    def press_enter(
        self,
    ) -> str:

        pyautogui.press(
            "enter"
        )

        return "Naciskam Enter."

    def _open_windows_url(
        self,
        url: str,
    ) -> bool:

        try:
            if os.name == "nt":
                os.startfile(url)
                return True
        except OSError:
            raise RuntimeError("AutoDev: przechwycony wyjątek")

        try:
            return bool(
                webbrowser.open(
                    url,
                    new=2,
                    autoraise=True,
                )
            )
        except webbrowser.Error:
            return False