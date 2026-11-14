"""Cuts chosen moments into vertical 1080x1920 clips with burned-in captions."""

import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

WIDTH, HEIGHT = 1080, 1920
MAX_CLIP_SECONDS = 180  # YouTube Shorts limit; Reels reach is best well under this
WORDS_PER_CAPTION = 4


class Clip(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    start: float = Field(ge=0)
    end: float
    title: str
    caption: str
    hashtags: list[str] = []
    why: str = Field(min_length=10, description="Why this moment works on its own.")
    layout: Literal["crop", "blur"] = "blur"
    captions: bool = True

    @model_validator(mode="after")
    def _length(self):
        length = self.end - self.start
        if length <= 0:
            raise ValueError(f"clip {self.id}: end must be after start")
        if length > MAX_CLIP_SECONDS:
            raise ValueError(f"clip {self.id}: {length:g}s is over the {MAX_CLIP_SECONDS}s limit")
        return self


class ClipPlan(BaseModel):
    rights: str = Field(
        min_length=10,
        description="Who owns the source footage and why we may post clips of it.",
    )
    clips: list[Clip] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self):
        ids = [clip.id for clip in self.clips]
        if len(set(ids)) != len(ids):
            raise ValueError("two clips share the same id")
        return self


def caption_chunks(transcript: list[dict], start: float, end: float) -> list[dict]:
    """Groups of a few words inside the clip, with times relative to the clip start."""
    words = [
        word for segment in transcript for word in segment.get("words", [])
        if word["start"] >= start and word["end"] <= end
    ]
    chunks = []
    for index in range(0, len(words), WORDS_PER_CAPTION):
        group = words[index: index + WORDS_PER_CAPTION]
        chunks.append({
            "start": round(group[0]["start"] - start, 2),
            "end": round(group[-1]["end"] - start, 2),
            "text": " ".join(word["word"] for word in group),
        })
    return chunks


def _timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    return f"{millis // 3600000:02d}:{millis // 60000 % 60:02d}:{millis // 1000 % 60:02d},{millis % 1000:03d}"


def to_srt(chunks: list[dict]) -> str:
    return "\n".join(
        f"{number}\n{_timestamp(chunk['start'])} --> {_timestamp(chunk['end'])}\n{chunk['text']}\n"
        for number, chunk in enumerate(chunks, 1)
    )


def video_filter(layout: str, srt_path: Path | None) -> str:
    if layout == "crop":
        # Fill the frame and cut off the sides.
        chain = (f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                 f"crop={WIDTH}:{HEIGHT}[framed]")
    else:
        # Keep the whole picture, centred over a blurred copy of itself.
        chain = (f"[0:v]split[a][b];"
                 f"[a]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                 f"crop={WIDTH}:{HEIGHT},boxblur=20:5[back];"
                 f"[b]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease[front];"
                 f"[back][front]overlay=(W-w)/2:(H-h)/2[framed]")
    if srt_path is None:
        return chain.replace("[framed]", "[out]")
    style = ("FontName=DejaVu Sans,Bold=1,FontSize=14,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=60")
    escaped = str(srt_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"{chain};[framed]subtitles='{escaped}':force_style='{style}'[out]"


def cut_clip(video: Path, clip: Clip, transcript: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = None
    if clip.captions:
        chunks = caption_chunks(transcript, clip.start, clip.end)
        if chunks:
            srt_path = out_dir / f"{clip.id}.srt"
            srt_path.write_text(to_srt(chunks), encoding="utf-8")
    out_path = out_dir / f"{clip.id}.mp4"
    command = [
        "ffmpeg", "-v", "error", "-y", "-ss", f"{clip.start}", "-i", str(video),
        "-t", f"{clip.end - clip.start}",
        "-filter_complex", video_filter(clip.layout, srt_path),
        "-map", "[out]", "-map", "0:a?", "-r", "30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on clip {clip.id}: {result.stderr.strip()[-500:]}")
    return out_path


def review_sheet(plan: ClipPlan, outputs: dict[str, Path]) -> str:
    lines = ["# Clips to review", f"**Rights:** {plan.rights}",
             "Nothing here has been posted. Approve each clip before it goes out."]
    for clip in plan.clips:
        lines.append(
            f"## {clip.id}: {clip.title}\n\n"
            f"- **File:** `{outputs[clip.id].name}`\n"
            f"- **Source time:** {clip.start:g}s to {clip.end:g}s ({clip.end - clip.start:g}s)\n"
            f"- **Why this moment:** {clip.why}\n"
            f"- **Caption:** {clip.caption}\n"
            f"- **Hashtags:** {' '.join(clip.hashtags)}"
        )
    return "\n\n".join(lines) + "\n"
