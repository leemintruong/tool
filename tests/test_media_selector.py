from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.media_selector import choose_media, distribute_scenes


class MediaSelectorTests(unittest.TestCase):
    def test_scene_distribution_uses_weights(self):
        scenes = [
            {"scene": 1, "weight": 0.75},
            {"scene": 2, "weight": 0.25},
        ]
        assigned = distribute_scenes(scenes, 4)
        self.assertEqual([scene["scene"] for scene in assigned if scene], [1, 1, 1, 2])

    def test_media_filename_is_matched_to_scene_keyword(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "kitchen_family.jpg").touch()
            (root / "hospital_hallway.png").touch()
            scenes = [{"scene": 1, "weight": 1.0, "keyword": "hospital hallway emotional scene"}]

            selected = choose_media(str(root), count=1, seed=42, scenes=scenes)

            self.assertEqual(selected[0].name, "hospital_hallway.png")


if __name__ == "__main__":
    unittest.main()
