import unittest

from factory_core.project_manager import extract_youtube_id


class ProjectManagerTests(unittest.TestCase):
    def test_extract_watch_id(self):
        self.assertEqual(
            extract_youtube_id("https://www.youtube.com/watch?v=Ce3G2LHKkNk"),
            "Ce3G2LHKkNk",
        )

    def test_extract_short_url_id(self):
        self.assertEqual(
            extract_youtube_id("https://youtu.be/Ce3G2LHKkNk?t=10"),
            "Ce3G2LHKkNk",
        )


if __name__ == "__main__":
    unittest.main()
