import json
from io import BytesIO
import os
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from factory_core.gemini_service import GeminiClient, GeminiError, GeminiQuotaError
from factory_core.rewrite_service import parse_generated_story


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class GeminiServiceTests(unittest.TestCase):
    def test_generate_parses_text_and_usage(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(
                {
                    "candidates": [
                        {
                            "finishReason": "STOP",
                            "content": {"parts": [{"text": "TITLE: New Story\nSCRIPT: Fresh text."}]},
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
                    "modelVersion": "gemini-3.1-flash-lite-001",
                    "responseId": "response-1",
                }
            )

        client = GeminiClient(api_key="test-key-that-is-long-enough", opener=opener, retries=0)
        result = client.generate("Write an original story")

        self.assertEqual(result.finish_reason, "STOP")
        self.assertEqual(result.response_id, "response-1")
        self.assertEqual(result.usage["promptTokenCount"], 100)
        self.assertIn("gemini-3.1-flash-lite:generateContent", captured["url"])
        self.assertEqual(captured["body"]["generationConfig"]["maxOutputTokens"], 32768)

    def test_missing_api_key_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            client = GeminiClient(opener=lambda *_args, **_kwargs: None, retries=0)
            with self.assertRaises(GeminiError):
                client.generate("hello")

    def test_parse_generated_story_removes_labels_and_code_fence(self):
        title, script = parse_generated_story(
            "```text\nTITLE: A Different Door\nSCRIPT:\nThe story begins here.\n```"
        )
        self.assertEqual(title, "A Different Door")
        self.assertEqual(script, "The story begins here.")

    def test_quota_error_has_resume_guidance(self):
        def opener(request, timeout):
            del timeout
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {},
                BytesIO(b'{"error":{"message":"quota exhausted"}}'),
            )

        client = GeminiClient(api_key="test-key-that-is-long-enough", opener=opener, retries=0)
        with self.assertRaisesRegex(GeminiQuotaError, "Wait for the quota window"):
            client.generate("hello")


if __name__ == "__main__":
    unittest.main()
