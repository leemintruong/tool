from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.subtitle_generator import _format_ts, create_srt_from_script


class SubtitleGeneratorTests(unittest.TestCase):
    def test_timestamp_rounding_carries_to_next_second(self):
        self.assertEqual(_format_ts(1.9996), "00:00:02,000")

    def test_subtitles_are_calibrated_to_audio_duration(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "script.txt"
            output = root / "subtitles.srt"
            script.write_text(
                "The first sentence is short. The second sentence contains several more words for timing.",
                encoding="utf-8",
            )

            create_srt_from_script(
                str(script),
                str(output),
                target_duration_seconds=12.345,
            )

            text = output.read_text(encoding="utf-8")
            self.assertIn("00:00:12,345", text)
            self.assertNotIn(",1000", text)


if __name__ == "__main__":
    unittest.main()
