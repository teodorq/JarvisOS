from __future__ import annotations

from app.ai.actions import ActionTypes
from app.ai.commands.base_command import BaseCommand


class OpenWebsiteCommand(BaseCommand):

    def parse(
        self,
        command: str,
    ):

        command = command.strip().lower()

        websites = {
            "youtube": "youtube",
            "google": "google",
            "facebook": "facebook",
            "github": "github",
            "gmail": "gmail",
            "chatgpt": "chatgpt",
        }

        for site, target in websites.items():
            phrases = (
                f"otwórz {site}",
                f"otworz {site}",
                f"wejdź na {site}",
                f"wejdz na {site}",
                f"uruchom {site}",
            )

            if command in phrases:
                return {
                    "action_type": (
                        ActionTypes.OPEN_WEBSITE
                    ),
                    "target": target,
                    "text": "",
                    "url": "",
                    "query": "",
                }

        return None


class GoogleSearchCommand(BaseCommand):

    PREFIXES = (
        "wyszukaj w google ",
        "szukaj w google ",
        "google ",
    )

    def parse(
        self,
        command: str,
    ):

        command = command.strip().lower()

        for prefix in self.PREFIXES:
            if command.startswith(prefix):
                query = command[
                    len(prefix):
                ].strip()

                if query:
                    return self._action(query)

        return None

    def _action(
        self,
        query: str,
    ) -> dict:

        return {
            "action_type": (
                ActionTypes.GOOGLE_SEARCH
            ),
            "target": "google",
            "text": "",
            "url": "",
            "query": query,
        }


class YouTubeSearchCommand(BaseCommand):

    PREFIXES = (
        "wyszukaj na youtube ",
        "szukaj na youtube ",
        "wyszukaj w youtube ",
        "szukaj w youtube ",
        "youtube ",
        "yt ",
    )

    def parse(
        self,
        command: str,
    ):

        command = command.strip().lower()

        for prefix in self.PREFIXES:
            if command.startswith(prefix):
                query = command[
                    len(prefix):
                ].strip()

                if query:
                    return self._action(query)

        return None

    def _action(
        self,
        query: str,
    ) -> dict:

        return {
            "action_type": (
                ActionTypes.YOUTUBE_SEARCH
            ),
            "target": "youtube",
            "text": "",
            "url": "",
            "query": query,
        }