from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .common import atomic_write_json, atomic_write_text, sha256_file

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


def ngrams(tokens: list[str], size: int) -> Counter[tuple[str, ...]]:
    if len(tokens) < size:
        return Counter()
    return Counter(tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1))


def validate_script(
    source_path: str | Path,
    script_path: str | Path,
    output_dir: str | Path,
    *,
    ngram_size: int = 8,
) -> dict:
    source_text = Path(source_path).read_text(encoding="utf-8-sig")
    script_text = Path(script_path).read_text(encoding="utf-8-sig")
    source_tokens = tokenize(source_text)
    script_tokens = tokenize(script_text)

    source_ngrams = ngrams(source_tokens, ngram_size)
    script_ngrams = ngrams(script_tokens, ngram_size)
    overlaps = source_ngrams.keys() & script_ngrams.keys()
    overlap_occurrences = sum(min(source_ngrams[item], script_ngrams[item]) for item in overlaps)
    denominator = max(sum(script_ngrams.values()), 1)
    ratio = overlap_occurrences / denominator

    matching_phrases = [" ".join(item) for item in sorted(overlaps)[:50]]
    level = "LOW"
    if ratio >= 0.08:
        level = "HIGH"
    elif ratio >= 0.025:
        level = "REVIEW"

    report = {
        "notice": "This is an editorial similarity check, not a legal determination or a guarantee against platform claims.",
        "source_word_count": len(source_tokens),
        "script_word_count": len(script_tokens),
        "ngram_size": ngram_size,
        "matching_ngram_types": len(overlaps),
        "matching_ngram_occurrences": overlap_occurrences,
        "script_overlap_ratio": round(ratio, 6),
        "review_level": level,
        "sample_matching_phrases": matching_phrases,
        "source_sha256": sha256_file(source_path),
        "script_sha256": sha256_file(script_path),
    }

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = atomic_write_json(destination / "originality_report.json", report)
    text = (
        "ORIGINALITY REVIEW\n"
        "==================\n"
        f"Source words: {report['source_word_count']}\n"
        f"Script words: {report['script_word_count']}\n"
        f"Exact {ngram_size}-word overlap ratio: {report['script_overlap_ratio']:.2%}\n"
        f"Review level: {level}\n\n"
        f"Notice: {report['notice']}\n\n"
        "Sample matching phrases:\n"
        + ("\n".join(f"- {item}" for item in matching_phrases) if matching_phrases else "- None found")
        + "\n"
    )
    text_path = atomic_write_text(destination / "originality_report.txt", text)
    report["json_path"] = str(json_path)
    report["text_path"] = str(text_path)
    return report
