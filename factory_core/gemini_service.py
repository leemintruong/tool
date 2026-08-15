from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class GeminiError(RuntimeError):
    pass


class GeminiQuotaError(GeminiError):
    pass


@dataclass(frozen=True)
class GeminiResult:
    text: str
    model: str
    finish_reason: str | None
    usage: dict[str, Any]
    response_id: str | None = None


def gemini_api_key_status() -> str:
    return "SET" if os.environ.get("GEMINI_API_KEY", "").strip() else "NOT_SET (run SETUP_GEMINI_FREE_WINDOWS.bat)"


def _response_error_message(payload: bytes, fallback: str) -> str:
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
        message = data.get("error", {}).get("message")
        if message:
            return str(message)
    except (TypeError, ValueError):
        pass
    text = payload.decode("utf-8", errors="replace").strip()
    return text[:1000] or fallback


class GeminiClient:
    """Small dependency-free client for Gemini's generateContent endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.85,
        max_output_tokens: int = 32768,
        retries: int = 4,
        timeout_seconds: int = 600,
        api_base: str = DEFAULT_API_BASE,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        selected_model = (model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
        if not MODEL_RE.fullmatch(selected_model):
            raise ValueError(f"Invalid Gemini model name: {selected_model!r}")
        if not 0.0 <= temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        self.api_key = (api_key or "").strip()
        self.model = selected_model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.retries = retries
        self.timeout_seconds = timeout_seconds
        self.api_base = api_base.rstrip("/")
        self._opener = opener
        self._sleeper = sleeper

    def _resolved_api_key(self) -> str:
        key = self.api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise GeminiError(
                "GEMINI_API_KEY is not configured. Run SETUP_GEMINI_FREE_WINDOWS.bat, "
                "close PowerShell, then open it again."
            )
        return key

    def generate(self, prompt: str) -> GeminiResult:
        if not prompt.strip():
            raise ValueError("Gemini prompt cannot be empty")

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "candidateCount": 1,
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        endpoint = f"{self.api_base}/{quote(self.model, safe='-._')}:generateContent"

        for attempt in range(self.retries + 1):
            request = Request(
                endpoint,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "x-goog-api-key": self._resolved_api_key(),
                    "User-Agent": "youtube-auto-factory/7.2",
                },
            )
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return self._parse_response(data)
            except HTTPError as exc:
                payload_bytes = exc.read()
                message = _response_error_message(payload_bytes, str(exc))
                retriable = exc.code in {429, 500, 502, 503, 504}
                if retriable and attempt < self.retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = self._retry_delay(attempt, retry_after)
                    print(f"Gemini temporarily unavailable ({exc.code}); retrying in {delay:.0f}s...")
                    self._sleeper(delay)
                    continue
                if exc.code == 429:
                    raise GeminiQuotaError(
                        "Gemini Free quota is currently exhausted. Wait for the quota window to reset, "
                        f"then run the command again. Details: {message}"
                    ) from exc
                raise GeminiError(f"Gemini API returned HTTP {exc.code}: {message}") from exc
            except URLError as exc:
                if attempt < self.retries:
                    delay = self._retry_delay(attempt, None)
                    print(f"Gemini connection failed; retrying in {delay:.0f}s...")
                    self._sleeper(delay)
                    continue
                raise GeminiError(f"Could not connect to Gemini API: {exc.reason}") from exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise GeminiError("Gemini API returned an unreadable response.") from exc

        raise GeminiError("Gemini request failed after all retries.")

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return max(1.0, min(float(retry_after), 120.0))
            except ValueError:
                pass
        return min(5.0 * (2**attempt), 60.0)

    def _parse_response(self, data: dict[str, Any]) -> GeminiResult:
        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            suffix = f" Block reason: {block_reason}." if block_reason else ""
            raise GeminiError(f"Gemini returned no candidate text.{suffix}")

        candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
        if not text:
            finish_reason = candidate.get("finishReason")
            raise GeminiError(f"Gemini returned an empty response. Finish reason: {finish_reason or 'unknown'}")

        return GeminiResult(
            text=text,
            model=str(data.get("modelVersion") or self.model),
            finish_reason=candidate.get("finishReason"),
            usage=data.get("usageMetadata") if isinstance(data.get("usageMetadata"), dict) else {},
            response_id=data.get("responseId"),
        )

