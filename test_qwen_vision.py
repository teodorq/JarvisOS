from app.vision.vision_ai import VisionAI


def main():
    print("=== TEST QWEN VISION / API CHAT ===")

    vision = VisionAI()

    print("Robię screenshot i analizuję ekran...")
    result = vision.analyze_screen()

    print("\n===== WYNIK =====\n")
    print(result)

    print("\n=== KONIEC TESTU ===")


if __name__ == "__main__":
    main()