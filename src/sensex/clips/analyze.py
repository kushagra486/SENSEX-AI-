"""Finds the moments in a long video most likely to work as short clips.

Three signals are measured per second: how loud the audio is, how often the
picture cuts, and how much is being said. Candidate clips start and end on
sentence boundaries and are ranked by those signals. The ranking is a
shortlist for a human or Claude to choose from, not a verdict.
"""

import json
import re
import subprocess
from pathlib import Path

import numpy as np

SAMPLE_RATE = 8000


def duration_seconds(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def loudness_per_second(video: Path) -> list[float]:
    """Audio level for each second, 0.0 (silence) to 1.0 (full scale)."""
    process = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-f", "s16le", "-"],
        stdout=subprocess.PIPE,
    )
    levels = []
    while chunk := process.stdout.read(SAMPLE_RATE * 2):
        samples = np.frombuffer(chunk[: len(chunk) // 2 * 2], dtype=np.int16).astype(np.float64)
        levels.append(float(np.sqrt(np.mean(samples**2)) / 32768) if len(samples) else 0.0)
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg could not read the audio of {video}")
    return levels


def scene_cut_times(video: Path, threshold: float = 0.3) -> list[float]:
    """Times (seconds) where the picture changes sharply."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-an",
         "-vf", f"fps=4,scale=160:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read the picture of {video}")
    return [float(match) for match in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def transcribe(video: Path, model_size: str = "small") -> list[dict]:
    """Spoken sentences with word timings. Empty when nobody speaks."""
    from faster_whisper import WhisperModel

    # Decode with ffmpeg ourselves: it handles more files than the library's own reader.
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    if not len(audio):
        return []
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, word_timestamps=True, vad_filter=True)
    return [
        {
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": [
                {"start": round(word.start, 2), "end": round(word.end, 2), "word": word.word.strip()}
                for word in segment.words or []
            ],
        }
        for segment in segments
    ]


def _windows_from_speech(segments: list[dict], min_len: float, max_len: float) -> list[tuple]:
    """Every run of whole sentences whose length fits the clip range."""
    windows = []
    for first in range(len(segments)):
        start = segments[first]["start"]
        for last in range(first, len(segments)):
            length = segments[last]["end"] - start
            if length > max_len:
                break
            if length >= min_len:
                windows.append((start, segments[last]["end"]))
    return windows


def _windows_from_grid(total: float, min_len: float, max_len: float, step: float = 5.0) -> list[tuple]:
    length = min(max_len, max(min_len, 30.0))
    windows, start = [], 0.0
    while start + min_len <= total:
        windows.append((start, min(start + length, total)))
        start += step
    return windows


def _zscores(values: list[float]) -> list[float]:
    array = np.array(values, dtype=np.float64)
    spread = array.std()
    return [0.0] * len(values) if spread == 0 else list((array - array.mean()) / spread)


def find_candidates(
    loudness: list[float],
    cuts: list[float],
    segments: list[dict],
    total: float,
    min_len: float = 20.0,
    max_len: float = 60.0,
    count: int = 12,
) -> list[dict]:
    """The top non-overlapping windows, best first."""
    windows = _windows_from_speech(segments, min_len, max_len) or _windows_from_grid(total, min_len, max_len)
    if not windows:
        return []

    rows = []
    for start, end in windows:
        length = end - start
        seconds = loudness[int(start): max(int(start) + 1, int(end))] or [0.0]
        words = sum(
            len(segment["text"].split())
            for segment in segments
            if segment["start"] >= start and segment["end"] <= end
        )
        rows.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "loudness": float(np.mean(seconds)),
            "peak": float(np.max(seconds)),
            "cuts_per_minute": sum(start <= cut < end for cut in cuts) / length * 60,
            "words_per_second": words / length,
        })

    keys = ("loudness", "peak", "cuts_per_minute", "words_per_second")
    scores = np.sum([_zscores([row[key] for row in rows]) for key in keys], axis=0)
    for row, score in zip(rows, scores):
        row["score"] = round(float(score), 2)
        for key in keys:
            row[key] = round(row[key], 3)

    chosen: list[dict] = []
    for row in sorted(rows, key=lambda row: row["score"], reverse=True):
        if all(row["end"] <= kept["start"] or row["start"] >= kept["end"] for kept in chosen):
            row["text"] = " ".join(
                segment["text"] for segment in segments
                if segment["start"] >= row["start"] and segment["end"] <= row["end"]
            )
            chosen.append(row)
            if len(chosen) == count:
                break
    return chosen


def analyze_video(video: Path, model_size: str = "small", min_len: float = 20.0,
                  max_len: float = 60.0) -> dict:
    total = duration_seconds(video)
    loudness = loudness_per_second(video)
    cuts = scene_cut_times(video)
    segments = transcribe(video, model_size)
    return {
        "video": str(video),
        "duration_seconds": round(total, 2),
        "has_speech": bool(segments),
        "scene_cuts": len(cuts),
        "candidates": find_candidates(loudness, cuts, segments, total, min_len, max_len),
        "transcript": segments,
    }
