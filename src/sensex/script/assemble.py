"""Joins the clips you generated into the finished video, following the script.

Put each generated clip in `<script folder>/clips/` named after its shot
(`S1.mp4`, `S2.mp4`...). Optional voiceover files go in `<script folder>/audio/`
with the same names (`S2.mp3`). On-screen text from the script is drawn on.
"""

import subprocess
import textwrap
from pathlib import Path

from sensex.script.package import ScriptPackage

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
VIDEO_TYPES = (".mp4", ".mov", ".webm", ".mkv")
AUDIO_TYPES = (".mp3", ".wav", ".m4a")


def _find(folder: Path, shot_id: str, types: tuple[str, ...]) -> Path | None:
    for extension in types:
        path = folder / f"{shot_id}{extension}"
        if path.exists():
            return path
    return None


def missing_clips(package: ScriptPackage, folder: Path) -> list[str]:
    return [shot.id for shot in package.shots if _find(folder / "clips", shot.id, VIDEO_TYPES) is None]


def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return bool(out.strip())


def _font() -> str:
    return subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"],
                          capture_output=True, text=True).stdout.strip()


def assemble(package: ScriptPackage, folder: Path) -> Path:
    missing = missing_clips(package, folder)
    if missing:
        raise FileNotFoundError(
            f"No clip for shot(s) {', '.join(missing)}. Expected files like "
            f"{folder / 'clips' / (missing[0] + '.mp4')}."
        )
    width, height = SIZES[package.aspect_ratio]
    work = folder / "build"
    work.mkdir(exist_ok=True)
    parts = []
    for shot in package.shots:
        clip = _find(folder / "clips", shot.id, VIDEO_TYPES)
        voice = _find(folder / "audio", shot.id, AUDIO_TYPES)
        length = f"{shot.duration_seconds}"
        # Fill the frame, then freeze the last frame if the clip is shorter than the shot.
        video = (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                 f"crop={width}:{height},fps=30,tpad=stop_mode=clone:stop_duration={length}")
        if shot.on_screen_text:
            text_file = work / f"{shot.id}.txt"
            text_file.write_text(textwrap.fill(shot.on_screen_text, 24), encoding="utf-8")
            video += (f",drawtext=fontfile='{_font()}':textfile='{text_file}':fontsize={width // 17}:"
                      f"fontcolor=white:borderw=5:bordercolor=black:line_spacing=12:"
                      f"x=(w-text_w)/2:y=h*0.12")
        video += "[v]"
        inputs = ["-i", str(clip)]
        if voice:
            inputs += ["-i", str(voice)]
            audio = "[1:a]apad[a]"
        elif _has_audio(clip):
            audio = "[0:a]apad[a]"
        else:
            inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
            audio = "[1:a]anull[a]"
        part = work / f"{shot.id}.mp4"
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", f"{video};{audio}",
             "-map", "[v]", "-map", "[a]", "-t", length,
             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "44100", "-ac", "2", str(part)],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed on shot {shot.id}: {result.stderr.strip()[-500:]}")
        parts.append(part)

    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{part.resolve()}'\n" for part in parts), encoding="utf-8")
    final = folder / "final.mp4"
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", "-movflags", "+faststart", str(final)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg could not join the shots: {result.stderr.strip()[-500:]}")
    return final
