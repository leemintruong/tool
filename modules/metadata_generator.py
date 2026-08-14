import json
import re
from pathlib import Path
from .text_utils import read_text


def _first_sentence(text: str) -> str:
    m = re.search(r"(.{20,180}?[.!?])\s", text + " ")
    return m.group(1).strip() if m else text[:160].strip()


def _safe_title(text: str) -> str:
    first = _first_sentence(text)
    title = first.replace('"', '').strip()
    if len(title) > 88:
        title = title[:85].rstrip() + "..."
    return title


def create_metadata(script_path: str, out_path: str) -> str:
    script = read_text(script_path)
    title = _safe_title(script)
    description = (
        f"{_first_sentence(script)}\n\n"
        "A dramatic American emotional story about family, betrayal, truth, and justice. "
        "Watch until the end for the twist."
    )
    tags = [
        "emotional story",
        "american story",
        "family betrayal",
        "dramatic story",
        "true story style",
        "justice story",
        "family drama",
        "storytime",
        "betrayal story",
        "moral story",
    ]
    data = {
        "title_draft": title,
        "description_draft": description,
        "tags": tags,
        "thumbnail_text_options": ["KICKED OUT", "FINAL WILL", "HE LIED", "SHE KNEW"],
        "upload_recommendation": "Upload as Private/Unlisted first, review manually, then publish.",
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
