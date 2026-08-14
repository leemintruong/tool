import re
from pathlib import Path
from typing import List


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_sentences(text: str) -> List[str]:
    text = clean_text(text)
    # Keep punctuation with each sentence.
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_sentences(sentences: List[str], max_chars: int = 180) -> List[str]:
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current += " " + sentence
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def estimate_duration_seconds(text: str, words_per_minute: int = 145) -> float:
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 1.0
    return max(1.8, len(words) / words_per_minute * 60)
