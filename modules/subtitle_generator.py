from pathlib import Path

from .text_utils import read_text, split_sentences, chunk_sentences, estimate_duration_seconds


def _format_ts(seconds: float) -> str:
    total_millis = int(round(max(0.0, seconds) * 1000))
    total, millis = divmod(total_millis, 1000)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def create_srt_from_script(
    script_path: str,
    out_path: str,
    words_per_minute: int = 145,
    target_duration_seconds: float | None = None,
) -> str:
    text = read_text(script_path)
    sentences = split_sentences(text)
    chunks = chunk_sentences(sentences, max_chars=150)

    estimated = [estimate_duration_seconds(chunk, words_per_minute=words_per_minute) for chunk in chunks]
    if target_duration_seconds is not None:
        if target_duration_seconds <= 0:
            raise ValueError("target_duration_seconds must be greater than zero")
        estimated_total = sum(estimated)
        if estimated_total > 0:
            scale = target_duration_seconds / estimated_total
            estimated = [duration * scale for duration in estimated]

    t = 0.0
    lines = []
    for idx, (chunk, dur) in enumerate(zip(chunks, estimated), start=1):
        start = t
        if target_duration_seconds is not None and idx == len(chunks):
            end = target_duration_seconds
        else:
            end = t + dur
        lines.append(str(idx))
        lines.append(f"{_format_ts(start)} --> {_format_ts(end)}")
        lines.append(chunk)
        lines.append("")
        t = end

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return out_path
