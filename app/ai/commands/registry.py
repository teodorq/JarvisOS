from app.ai.commands.autodev_commands import AutoDevCommand
from app.ai.commands.browser_commands import (
    GoogleSearchCommand,
    OpenWebsiteCommand,
    YouTubeSearchCommand
)
from app.ai.commands.code_commands import CodeCommand
from app.ai.commands.desktop_commands import DesktopCommand
from app.ai.commands.memory_commands import MemoryCommand
from app.ai.commands.system_commands import SystemCommand
from app.ai.commands.vision_commands import VisionCommand
from app.ai.commands.windows_commands import WindowsCommand


class CommandRegistry:

    def __init__(self):
        self.commands = [
            SystemCommand(),
            AutoDevCommand(),
            CodeCommand(),
            WindowsCommand(),
            DesktopCommand(),
            OpenWebsiteCommand(),
            GoogleSearchCommand(),
            YouTubeSearchCommand(),
            VisionCommand(),
            MemoryCommand(),
        ]

    def parse(self, command: str):
        for parser in self.commands:
            action = parser.parse(command)

            if action:
                return action

        return None