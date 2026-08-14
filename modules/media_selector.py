import random
import re
from pathlib import Path
from typing import Any, List

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


def list_media(media_dir: str) -> List[Path]:
    root = Path(media_dir)
    files = []
    for p in root.rglob("*"):
        if p.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
            files.append(p)
    return files


def distribute_scenes(scenes: list[dict[str, Any]], count: int) -> list[dict[str, Any] | None]:
    """Map render slots to scene-plan entries using each scene's word weight."""
    if count <= 0:
        return []
    if not scenes:
        return [None] * count

    weights = [max(0.0, float(scene.get("weight") or 0.0)) for scene in scenes]
    total = sum(weights)
    if total <= 0:
        weights = [1.0] * len(scenes)
        total = float(len(scenes))

    cumulative: list[float] = []
    running = 0.0
    for weight in weights:
        running += weight / total
        cumulative.append(running)

    assigned: list[dict[str, Any]] = []
    scene_index = 0
    for slot in range(count):
        midpoint = (slot + 0.5) / count
        while scene_index < len(cumulative) - 1 and midpoint > cumulative[scene_index]:
            scene_index += 1
        assigned.append(scenes[scene_index])
    return assigned


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", value) if len(token) >= 3}


def _media_score(path: Path, scene: dict[str, Any] | None, root: Path) -> int:
    if not scene:
        return 0
    scene_tokens = _tokens(f"{scene.get('keyword', '')} {scene.get('text_preview', '')}")
    media_tokens = _tokens(str(path.relative_to(root)))
    return len(scene_tokens & media_tokens)


def choose_media(
    media_dir: str,
    count: int,
    seed: int = 42,
    scenes: list[dict[str, Any]] | None = None,
) -> List[Path]:
    files = list_media(media_dir)
    if not files:
        raise FileNotFoundError(f"No image/video files found in: {media_dir}")

    root = Path(media_dir).resolve()
    files = sorted((path.resolve() for path in files), key=lambda path: path.as_posix().casefold())
    rng = random.Random(seed)
    fallback = files[:]
    rng.shuffle(fallback)
    slots = distribute_scenes(scenes or [], count)

    selected: list[Path] = []
    for index, scene in enumerate(slots):
        scores = [(path, _media_score(path, scene, root)) for path in files]
        best_score = max((score for _path, score in scores), default=0)
        if best_score > 0:
            candidates = [path for path, score in scores if score == best_score]
            choice = candidates[index % len(candidates)]
        else:
            choice = fallback[index % len(fallback)]

        if len(files) > 1 and selected and choice == selected[-1]:
            alternatives = [path for path in fallback if path != selected[-1]]
            if alternatives:
                choice = alternatives[index % len(alternatives)]
        selected.append(choice)
    return selected
