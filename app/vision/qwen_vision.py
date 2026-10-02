import base64
from io import BytesIO
import json
import urllib.request
import urllib.error
from PIL import Image


class QwenVision:
    def __init__(self, model: str = "qwen2.5vl:7b"):
        self.model = model
        self.url = "http://127.0.0.1:11434/api/chat"

    def analyze_image(self, image_path: str) -> str:
        prompt = "Opisz po polsku krótko, co widzisz na ekranie komputera."
        return self._chat_with_image(image_path, prompt)

    def ask_about_image(self, image_path: str, question: str) -> str:
        return self._chat_with_image(image_path, question)

    def _chat_with_image(self, image_path: str, prompt: str) -> str:
        try:
            image_base64 = self._encode_optimized_image(image_path)

            payload = {
                "model": self.model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_base64]
                    }
                ],
                "options": {
                    "num_ctx": 4096,
                    "temperature": 0.1,
                    "top_p": 0.8
                }
            }

            request = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read().decode("utf-8", errors="ignore")
                data = json.loads(raw)

                message = data.get("message", {})
                content = message.get("content", "").strip()

                if content:
                    return content

                return f"Qwen Vision nie zwrócił treści. Surowa odpowiedź:\n{raw}"

        except FileNotFoundError:
            return f"BŁĄD Qwen Vision: Nie znaleziono obrazu: {image_path}"

        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="ignore")
            return f"BŁĄD HTTP Qwen Vision: {error.code}\n{details}"

        except urllib.error.URLError as error:
            return f"BŁĄD POŁĄCZENIA Qwen Vision: {error}"

        except Exception as error:
            return f"BŁĄD Qwen Vision: {error}"

    @staticmethod
    def _encode_optimized_image(image_path: str) -> str:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        max_width = 960
        width, height = image.size
        if width > max_width:
            ratio = max_width / width
            new_height = int(height * ratio)
            image = image.resize((max_width, new_height))
        output = BytesIO()
        image.save(output, "JPEG", quality=60, optimize=True)
        return base64.b64encode(output.getvalue()).decode("utf-8")
