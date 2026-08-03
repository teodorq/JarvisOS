from __future__ import annotations

import json
from pathlib import Path
import sys
import time


def _show(event: dict) -> None:
    stage = str(event.get("stage", "PRACA"))
    moment = str(event.get("time", ""))[-8:]
    message = str(event.get("message", ""))
    print(f"[{moment}] {stage}: {message}", flush=True)
    details = dict(event.get("details", {}) or {})
    for index, item in enumerate(list(details.get("plan", []) or []), 1):
        print(f"  {index}. {item}", flush=True)


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    path = Path(sys.argv[1]).resolve(strict=False)
    print("JARVIS — KONSOLA SAMOROZWOJU PYTHONA", flush=True)
    print("Pokazuję rzeczywisty przebieg zatwierdzonej pracy.\n", flush=True)
    position = 0
    deadline = time.monotonic() + 60 * 60
    terminal = False
    while time.monotonic() < deadline and not terminal:
        try:
            with path.open("r", encoding="utf-8") as stream:
                stream.seek(position)
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    position = stream.tell()
                    try:
                        event = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    _show(dict(event))
                    terminal = bool(event.get("terminal", False))
                    if terminal:
                        break
        except OSError:
            pass
        if not terminal:
            time.sleep(0.2)
    if terminal:
        print("\nPraca zakończona. Okno zamknie się za 4 sekundy.", flush=True)
        time.sleep(4.0)
        return 0
    print("\nMonitor zakończył oczekiwanie.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
