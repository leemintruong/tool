from __future__ import annotations

import html
import json
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .common import atomic_write_json, atomic_write_text

TIMESTAMP_RE = re.compile(
    r"(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{2}):(?P<seconds>\d{2})[.,](?P<millis>\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
STAGE_RE = re.compile(
    r"(?:^|\s)(?:\[[^\]]*(?:music|applause|laughter|noise|silence)[^\]]*\]|"
    r"\([^)]*(?:music|applause|laughter|noise|silence)[^)]*\))(?:\s|$)",
    re.IGNORECASE,
)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def parse_timestamp(value: str) -> float:
    match = TIMESTAMP_RE.search(value.strip())
    if not match:
        return 0.0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis"))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def clean_caption_text(text: str) -> str:
    value = html.unescape(text)
    value = TAG_RE.sub(" ", value)
    value = value.replace("\u200b", " ").replace("\ufeff", " ")
    value = value.replace("♪", " ").replace("♫", " ")
    value = STAGE_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def parse_vtt_or_srt(path: str | Path) -> list[TranscriptSegment]:
    lines = Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
    segments: list[TranscriptSegment] = []
    index = 0

    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue

        start_raw, end_raw = line.split("-->", 1)
        start = parse_timestamp(start_raw)
        end = parse_timestamp(end_raw)
        index += 1

        cue_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            cue_lines.append(lines[index].strip())
            index += 1

        text = clean_caption_text(" ".join(cue_lines))
        if text:
            segments.append(TranscriptSegment(start=start, end=max(end, start), text=text))
        index += 1
    return segments


def _xml_time(value: str | None) -> float:
    if not value:
        return 0.0
    value = value.strip()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000
    if value.endswith("s") and value[:-1].replace(".", "", 1).isdigit():
        return float(value[:-1])
    return parse_timestamp(value)


def parse_ttml(path: str | Path) -> list[TranscriptSegment]:
    root = ET.parse(path).getroot()
    segments: list[TranscriptSegment] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() != "p":
            continue
        text = clean_caption_text(" ".join(element.itertext()))
        if not text:
            continue
        start = _xml_time(element.attrib.get("begin"))
        end = _xml_time(element.attrib.get("end"))
        if not end and element.attrib.get("dur"):
            end = start + _xml_time(element.attrib.get("dur"))
        segments.append(TranscriptSegment(start=start, end=max(end, start), text=text))
    return segments


def parse_json3(path: str | Path) -> list[TranscriptSegment]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    segments: list[TranscriptSegment] = []
    for event in data.get("events") or []:
        pieces = []
        for item in event.get("segs") or []:
            value = item.get("utf8")
            if value:
                pieces.append(value)
        text = clean_caption_text("".join(pieces))
        if not text:
            continue
        start = float(event.get("tStartMs") or 0) / 1000
        duration = float(event.get("dDurationMs") or 0) / 1000
        segments.append(TranscriptSegment(start=start, end=start + duration, text=text))
    return segments


def parse_subtitle(path: str | Path) -> list[TranscriptSegment]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".vtt", ".srt"}:
        return parse_vtt_or_srt(source)
    if suffix == ".json3":
        return parse_json3(source)
    if suffix in {".ttml", ".srv3", ".xml"}:
        return parse_ttml(source)

    text = clean_caption_text(source.read_text(encoding="utf-8-sig", errors="replace"))
    return [TranscriptSegment(start=0.0, end=0.0, text=text)] if text else []


def _comparison_token(word: str) -> str:
    return re.sub(r"(^\W+|\W+$)", "", word, flags=re.UNICODE).casefold()


def merge_rolling_captions(segments: Iterable[TranscriptSegment]) -> str:
    output_words: list[str] = []
    output_keys: list[str] = []

    for segment in segments:
        words = segment.text.split()
        keys = [_comparison_token(word) for word in words]
        pairs = [(word, key) for word, key in zip(words, keys) if key]
        if not pairs:
            continue
        words = [pair[0] for pair in pairs]
        keys = [pair[1] for pair in pairs]

        max_overlap = min(len(output_keys), len(keys), 80)
        overlap = 0
        for size in range(max_overlap, 0, -1):
            if output_keys[-size:] == keys[:size]:
                overlap = size
                break

        if overlap == 0 and output_keys:
            recent = output_keys[-120:]
            if len(keys) <= len(recent):
                for start in range(0, len(recent) - len(keys) + 1):
                    if recent[start : start + len(keys)] == keys:
                        overlap = len(keys)
                        break

        if overlap < len(words):
            output_words.extend(words[overlap:])
            output_keys.extend(keys[overlap:])
    return SPACE_RE.sub(" ", " ".join(output_words)).strip()


def make_paragraphs(text: str, target_chars: int = 650) -> str:
    value = SPACE_RE.sub(" ", text).strip()
    if not value:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", value)
    if len(sentences) == 1:
        words = value.split()
        chunks = [" ".join(words[index : index + 110]) for index in range(0, len(words), 110)]
        return "\n\n".join(chunks)

    paragraphs: list[str] = []
    current: list[str] = []
    current_size = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        addition = len(sentence) + (1 if current else 0)
        if current and current_size + addition > target_chars:
            paragraphs.append(" ".join(current))
            current = []
            current_size = 0
        current.append(sentence)
        current_size += addition
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def format_clock(seconds: float) -> str:
    millis = int(round(max(seconds, 0) * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def write_transcript_outputs(
    project_dir: str | Path,
    segments: list[TranscriptSegment],
    *,
    source_kind: str,
    source_file: str | Path | None = None,
) -> dict[str, str | int]:
    directory = Path(project_dir).resolve()
    transcript_dir = directory / "transcript"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    raw_text = "\n".join(segment.text for segment in segments).strip()
    merged = merge_rolling_captions(segments)
    clean_text = make_paragraphs(merged)
    timed_text = "\n".join(
        f"[{format_clock(segment.start)} --> {format_clock(segment.end)}] {segment.text}"
        for segment in segments
    )

    raw_path = atomic_write_text(transcript_dir / "transcript_raw.txt", raw_text + ("\n" if raw_text else ""))
    clean_path = atomic_write_text(transcript_dir / "transcript_clean.txt", clean_text + ("\n" if clean_text else ""))
    timed_path = atomic_write_text(transcript_dir / "transcript_timed.txt", timed_text + ("\n" if timed_text else ""))
    json_path = atomic_write_json(
        transcript_dir / "transcript_segments.json",
        {
            "source_kind": source_kind,
            "source_file": str(source_file) if source_file else None,
            "segment_count": len(segments),
            "segments": [asdict(segment) for segment in segments],
        },
    )

    return {
        "raw": str(raw_path),
        "clean": str(clean_path),
        "timed": str(timed_path),
        "segments": str(json_path),
        "segment_count": len(segments),
        "word_count": len(clean_text.split()),
    }
