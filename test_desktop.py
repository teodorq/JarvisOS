print("START")

from app.desktop.controller import DesktopController

print("Import OK")

jarvis = DesktopController()

print("Obiekt utworzony")

print("Test za 5 sekund...")
jarvis.wait(5)

print("Ruszam myszką...")

jarvis.move_mouse(500, 500)

print("Klikam...")

jarvis.click()

print("KONIEC")