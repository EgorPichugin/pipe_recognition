import json
import re
from typing import Any

from src.core.config import GEMINI_API_KEY, GEMINI_MODEL


class GeminiUnavailableError(RuntimeError):
    pass


class GeminiError(RuntimeError):
    pass


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


def parse_json_response(text: str) -> Any:
    cleaned = _strip_json_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


class GeminiClient:
    def __init__(self, api_key: str | None = GEMINI_API_KEY, model: str = GEMINI_MODEL) -> None:
        self._api_key = api_key
        self._model_name = model
        self._model: Any | None = None

    def generate_json(self, instructions: str, payload: dict[str, Any]) -> Any:
        if not self._api_key:
            raise GeminiUnavailableError("GEMINI_API_KEY is not configured.")

        prompt = (
            f"{instructions}\n\n"
            "Respond with a single JSON object only. No prose, no markdown fences.\n\n"
            "INPUT:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        try:
            response = self._get_model().generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                },
            )
        except GeminiUnavailableError:
            raise
        except Exception as exc:
            raise GeminiError(f"Gemini request failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise GeminiError("Gemini returned an empty response.")

        try:
            return parse_json_response(text)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"Gemini response was not valid JSON: {exc}") from exc

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                import google.generativeai as genai
            except ModuleNotFoundError as exc:
                raise GeminiUnavailableError(
                    "google-generativeai is not installed. Run pip install -r requirements.txt.",
                ) from exc

            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
        return self._model
