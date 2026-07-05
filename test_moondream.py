from app.vision.screen import ScreenVision
from app.vision.moondream import MoondreamVision

print("=== START ===")

screen = ScreenVision()
vision = MoondreamVision()

print("Robię screenshot...")
image = screen.take_screenshot()

print("Screenshot:", image)

print("Analizuję obraz...")
result = vision.analyze(image)

print("\n===== WYNIK =====")
print(result)

print("=== KONIEC ===")