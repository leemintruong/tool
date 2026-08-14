from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .common import atomic_write_json, atomic_write_text, read_json, utc_now_iso

DEFAULT_PROFILE = Path("config/profiles/family_drama_us.yaml")


def load_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Prompt profile not found: {source}")
    with source.open("r", encoding="utf-8-sig") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Prompt profile must contain a YAML object: {source}")
    data["_profile_path"] = str(source)
    return data


def _list_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_rewrite_prompt(
    project_dir: str | Path,
    *,
    profile_path: str | Path = DEFAULT_PROFILE,
) -> Path:
    directory = Path(project_dir).resolve()
    transcript_path = directory / "transcript" / "transcript_clean.txt"
    metadata_path = directory / "source" / "metadata.json"

    if not transcript_path.is_file():
        raise FileNotFoundError(f"Clean transcript not found: {transcript_path}")

    transcript = transcript_path.read_text(encoding="utf-8-sig").strip()
    metadata = read_json(metadata_path, default={}) or {}
    profile = load_profile(profile_path)

    originality_rules = profile.get("originality_rules") or []
    safety_rules = profile.get("safety_rules") or []
    structure = profile.get("story_structure") or []
    output_rules = profile.get("output_rules") or []

    prompt = f"""You are creating a genuinely original script inspired only by the broad genre, audience expectations, pacing lessons, and emotional mechanics of a reference transcript.

IMPORTANT RIGHTS AND ORIGINALITY RULE
The source below is research material only. Do not reproduce it, lightly paraphrase it, translate it, or preserve its distinctive sequence of events. Create a new work with new expression, new characters, new setting, new motives, new key events, new dialogue, and a materially different resolution.

TARGET PROFILE
- Profile: {profile.get('name', 'family_drama_us')}
- Output language: {profile.get('output_language', 'English')}
- Audience: {profile.get('audience', 'US family-drama viewers')}
- Target length: {profile.get('target_words_min', 2500)} to {profile.get('target_words_max', 3500)} words
- Narrative voice: {profile.get('narrative_voice', 'first-person past tense')}
- Tone: {profile.get('tone', 'emotionally engaging but credible')}

ORIGINALITY REQUIREMENTS
{_list_lines([str(item) for item in originality_rules])}

SAFETY AND BRAND-SUITABILITY REQUIREMENTS
{_list_lines([str(item) for item in safety_rules])}

STORY STRUCTURE
{_list_lines([str(item) for item in structure])}

OUTPUT RULES
{_list_lines([str(item) for item in output_rules])}

REFERENCE METADATA
Reference title: {metadata.get('title') or 'Unknown'}
Reference channel: {metadata.get('channel') or metadata.get('uploader') or 'Unknown'}
Reference duration: {metadata.get('duration') or 'Unknown'} seconds

REFERENCE TRANSCRIPT — FOR ABSTRACT ANALYSIS ONLY
<<<REFERENCE_TRANSCRIPT
{transcript}
REFERENCE_TRANSCRIPT

Before writing, silently reduce the reference to abstract observations such as hook speed, tension curve, scene density, and emotional progression. Then discard its specific expression and plot sequence.

Return only the requested original title and original script. Do not include analysis, similarity commentary, policy discussion, or the reference transcript in your answer.
"""

    prompts_dir = directory / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = atomic_write_text(prompts_dir / "rewrite_prompt.txt", prompt)
    atomic_write_json(
        prompts_dir / "prompt_manifest.json",
        {
            "created_at": utc_now_iso(),
            "profile": profile.get("name"),
            "profile_path": profile.get("_profile_path"),
            "reference_title": metadata.get("title"),
            "reference_word_count": len(transcript.split()),
            "prompt_path": str(prompt_path),
        },
    )
    return prompt_path
