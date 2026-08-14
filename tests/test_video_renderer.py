from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.video_renderer import _clean_intermediate_outputs, _escape_subtitle_filter_path


class VideoRendererTests(unittest.TestCase):
    def test_windows_subtitle_path_is_escaped_for_ffmpeg(self):
        escaped = _escape_subtitle_filter_path(r"C:\Users\O'Brien\captions.srt")
        self.assertEqual(escaped, r"C\:/Users/O\'Brien/captions.srt")

    def test_cleanup_preserves_previous_final_video(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            segments = root / "segments"
            segments.mkdir()
            (segments / "segment_0001.mp4").touch()
            (segments / "notes.txt").touch()
            (root / "video_silent.mp4").touch()
            (root / "final_video.mp4").touch()

            _clean_intermediate_outputs(root, segments)

            self.assertFalse((segments / "segment_0001.mp4").exists())
            self.assertTrue((segments / "notes.txt").exists())
            self.assertFalse((root / "video_silent.mp4").exists())
            self.assertTrue((root / "final_video.mp4").exists())


if __name__ == "__main__":
    unittest.main()
