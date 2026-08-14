import json
import re
from pathlib import Path
from typing import List, Dict

from .text_utils import read_text


def _split_paragraphs(text: str) -> List[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) >= 8:
        return blocks
    # Fallback: split by sentences and group every 3 sentences.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    grouped = []
    for i in range(0, len(sentences), 3):
        grouped.append(" ".join(sentences[i:i+3]))
    return grouped or [text.strip()]


_KEYWORDS = [
    (r"mother|mom|elderly|old woman|widow", "elderly American woman emotional portrait"),
    (r"son|daughter|children|family", "American family argument living room"),
    (r"house|home|door|porch|neighborhood", "suburban American house exterior"),
    (r"lawyer|attorney|will|document|signature|legal", "lawyer office documents close up"),
    (r"hospital|doctor|nurse|clinic", "hospital hallway emotional scene"),
    (r"court|judge|trial", "courtroom legal drama"),
    (r"wedding|bride|groom", "American wedding emotional drama"),
    (r"Christmas|Thanksgiving", "American holiday family dinner emotional"),
    (r"rain|night|street", "rainy night lonely street cinematic"),
]


def _guess_keyword(text: str) -> str:
    low = text.lower()
    for pattern, keyword in _KEYWORDS:
        if re.search(pattern, low):
            return keyword
    return "cinematic emotional American family drama"


def create_scene_plan(script_path: str, out_json: str, target_scenes: int = 25) -> str:
    if target_scenes <= 0:
        raise ValueError("target_scenes must be greater than zero")
    text = read_text(script_path)
    blocks = _split_paragraphs(text)

    # If there are too many blocks, combine them without dropping the tail.
    if len(blocks) > target_scenes:
        base_size, larger_chunks = divmod(len(blocks), target_scenes)
        combined: list[str] = []
        cursor = 0
        for index in range(target_scenes):
            size = base_size + (1 if index < larger_chunks else 0)
            combined.append("\n".join(blocks[cursor : cursor + size]))
            cursor += size
        blocks = combined

    total_words = max(1, len(re.findall(r"\w+", text)))
    scenes: List[Dict] = []
    for idx, block in enumerate(blocks, start=1):
        words = len(re.findall(r"\w+", block))
        weight = words / total_words
        scenes.append({
            "scene": idx,
            "text_preview": block[:240].replace("\n", " ") + ("..." if len(block) > 240 else ""),
            "keyword": _guess_keyword(block),
            "weight": round(weight, 4),
        })

    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_json
