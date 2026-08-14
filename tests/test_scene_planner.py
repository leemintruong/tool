import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.scene_planner import create_scene_plan


class ScenePlannerTests(unittest.TestCase):
    def test_combining_blocks_does_not_drop_the_tail(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "script.txt"
            output = root / "scenes.json"
            script.write_text(
                "\n\n".join(f"Paragraph {index}." for index in range(30)),
                encoding="utf-8",
            )

            create_scene_plan(str(script), str(output), target_scenes=25)

            scenes = json.loads(output.read_text(encoding="utf-8"))["scenes"]
            self.assertEqual(len(scenes), 25)
            self.assertIn("Paragraph 29.", " ".join(scene["text_preview"] for scene in scenes))


if __name__ == "__main__":
    unittest.main()
