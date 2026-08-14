from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from factory_core.transcript_service import merge_rolling_captions, parse_vtt_or_srt


class TranscriptTests(unittest.TestCase):
    def test_rolling_caption_deduplication(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "sample.vtt"
            path.write_text(
                "WEBVTT\n\n"
                "00:00:00.000 --> 00:00:02.000\nMy name is Savannah.\n\n"
                "00:00:01.500 --> 00:00:04.000\nMy name is Savannah. I am 28 years old.\n\n"
                "00:00:04.000 --> 00:00:06.000\nI am 28 years old. I live in Georgia.\n",
                encoding="utf-8",
            )
            segments = parse_vtt_or_srt(path)
            merged = merge_rolling_captions(segments)
            self.assertEqual(
                merged,
                "My name is Savannah. I am 28 years old. I live in Georgia.",
            )


if __name__ == "__main__":
    unittest.main()
