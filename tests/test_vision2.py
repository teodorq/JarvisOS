import time
from pprint import pprint

from app.vision.screen import ScreenVision
from app.vision2.vision_brain import VisionBrain


def main():
    brain = VisionBrain(ScreenVision())

    print()
    print("========== VISION BRAIN TEST 1 ==========")
    result1 = brain.analyze()
    pprint(result1)
    print("=========================================")

    print()
    print("Porusz myszką. Czekam 3 sekundy...")
    time.sleep(3)

    print()
    print("========== VISION BRAIN TEST 2 ==========")
    result2 = brain.analyze()
    pprint(result2)
    print("=========================================")
    print()


if __name__ == "__main__":
    main()