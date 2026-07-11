import base64
import json
import urllib.request
import urllib.error
from pathlib import Path
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
            optimized_path = self._optimize_image(image_path)
            image_base64 = self._encode_image(optimized_path)

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

    def _optimize_image(self, image_path: str) -> str:
        path = Path(image_path)
        output_path = str(path.with_name(path.stem + "_optimized.jpg"))

        image = Image.open(image_path).convert("RGB")

        max_width = 960
        width, height = image.size

        if width > max_width:
            ratio = max_width / width
            new_height = int(height * ratio)
            image = image.resize((max_width, new_height))

        image.save(output_path, "JPEG", quality=60, optimize=True)

        return output_path

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")