"""Generates everything one script needs: character references, frames, clips, voice lines."""

import re
import subprocess
from pathlib import Path

from sensex.config import ROOT
from sensex.generate import huggingface as hf
from sensex.script.package import ScriptPackage, Shot
from sensex.script.series import slug


def identity_dir(package: ScriptPackage, folder: Path, root: Path = ROOT) -> Path:
    """Where a script's character references and voice samples live.

    A series keeps them in its own folder so every episode reuses them.
    """
    if package.series:
        return root / "series" / slug(package.series.title)
    return folder


def spoken_line(shot: Shot) -> tuple[str, str] | None:
    """(speaker, words) for the shot's dialogue, or its voiceover if there is no dialogue."""
    line = shot.dialogue or shot.voiceover
    if not line.strip():
        return None
    match = re.match(r"\s*([^:]{1,40}):\s*(.+)", line, re.S)
    speaker, words = (match.group(1), match.group(2)) if match else ("Narrator", line)
    return speaker.strip(), words.strip().strip('"')


def _seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def generate_shot(package: ScriptPackage, shot: Shot, folder: Path, redo: bool = False,
                  video: bool = True, voice: bool = True, root: Path = ROOT) -> list[str]:
    """Make the missing files for one shot. Returns a line per thing done or skipped."""
    notes = []
    identity = identity_dir(package, folder, root)
    characters = {character.id: character for character in package.characters}

    clip = folder / "clips" / f"{shot.id}.mp4"
    if video and (redo or not clip.exists()):
        frame = folder / "frames" / f"{shot.id}.png"
        if redo or not frame.exists():
            lead = characters.get(shot.characters[0]) if shot.characters else None
            if lead:
                reference = identity / "refs" / f"{lead.id}.png"
                if not reference.exists():
                    hf.make_frame(lead.reference_image_prompt, reference, package.aspect_ratio)
                    notes.append(f"made reference image for {lead.name}")
                hf.edit_frame(reference, shot.prompt, frame)
            else:
                hf.make_frame(shot.prompt, frame, package.aspect_ratio)
        hf.animate(frame, shot.prompt, shot.duration_seconds, clip)
        short = shot.duration_seconds > hf.MAX_CLIP_SECONDS
        notes.append(f"clip {clip.name}" + (f" ({hf.MAX_CLIP_SECONDS}s of a {shot.duration_seconds:g}s shot; "
                                             "the last frame is held when assembled)" if short else ""))
    elif video:
        notes.append(f"clip {clip.name} already exists, skipped")

    line = spoken_line(shot)
    audio = folder / "audio" / f"{shot.id}.wav"
    if voice and line and (redo or not audio.exists()):
        speaker, words = line
        sample = identity / "voices" / f"{slug(speaker)}.wav"
        hf.speak(words, audio, sample if sample.exists() else None)
        if not sample.exists():
            # The first line a speaker says becomes their voice for every later line.
            sample.parent.mkdir(parents=True, exist_ok=True)
            sample.write_bytes(audio.read_bytes())
            notes.append(f"set {speaker}'s voice from this line")
        length = _seconds(audio)
        notes.append(f"voice {audio.name} ({length:.1f}s)" + (
            f"; longer than the {shot.duration_seconds:g}s shot, so it will be cut off" if
            length > shot.duration_seconds else ""))
    return notes
