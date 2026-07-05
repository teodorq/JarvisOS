import base64
import json
import urllib.request
import urllib.error


class MoondreamVision:
    def __init__(self, model: str = "moondream"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def analyze(self, image_path: str) -> str:
        prompt = """
Describe this computer screen in detail.

Answer in Polish.

Tell:
- what applications are visible,
- what windows are open,
- what text you can read,
- whether there are errors,
- what the user is probably doing.
"""

        try:
            with open(image_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

            data = {
                "model": self.model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False
            }

            request = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
                answer = result.get("response", "").strip()

                if not answer:
                    return "Vision AI nie zwrócił odpowiedzi."

                return answer

        except FileNotFoundError:
            return f"BŁĄD Vision AI: Nie znaleziono obrazu: {image_path}"

        except urllib.error.URLError:
            return "BŁĄD: Ollama nie działa. Uruchom Ollama i spróbuj ponownie."

        except Exception as error:
            return f"BŁĄD Vision AI: {error}"