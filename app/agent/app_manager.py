import os
import subprocess


class AppManager:

    def open_notepad(self):
        os.system("notepad")
        return "Otwieram Notatnik."

    def open_steam(self):
        os.system("start steam://open/main")
        return "Otwieram Steam."

    def open_discord(self):
        try:
            subprocess.Popen(
                r"C:\Users\Kacperek\AppData\Local\Discord\Update.exe --processStart Discord.exe"
            )
            return "Otwieram Discord."
        except Exception:
            return "Nie udało się otworzyć Discorda."

    def open_opera(self):
        opera = (
            r"C:\Users\Kacperek\AppData\Local\Programs"
            r"\Opera GX\opera.exe"
        )

        subprocess.Popen([opera])
        return "Otwieram Opera GX."

    def open_app(self, name: str):
        name = name.lower().strip()

        if name in ["opera", "opera gx", "chrome", "gx"]:
            return self.open_opera()

        if name == "notatnik":
            return self.open_notepad()

        if name == "steam":
            return self.open_steam()

        if name == "discord":
            return self.open_discord()

        return f"Nie znam aplikacji: {name}"