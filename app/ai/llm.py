import json
import urllib.request
import urllib.error


class LocalLLM:
    def __init__(self, model: str = "qwen2.5:3b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def ask(self, prompt: str) -> str:
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        try:
            request = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", "").strip()

        except urllib.error.URLError:
            return "BŁĄD: Ollama nie działa. Uruchom Ollama i spróbuj ponownie."

        except Exception as error:
            return f"BŁĄD LLM: {error}"