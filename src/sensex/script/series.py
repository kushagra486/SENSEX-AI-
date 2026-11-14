"""The series bible: one file per series that keeps characters and story consistent.

`series/<slug>/bible.json` holds each character's fixed description and a log
of every episode. New episodes are checked against it, then recorded into it.
"""

import re
from pathlib import Path

from pydantic import BaseModel

from sensex.config import ROOT
from sensex.script.package import Character, ScriptPackage


class Episode(BaseModel):
    number: int
    title: str
    summary: str
    cliffhanger: str


class Bible(BaseModel):
    title: str
    season_arc: str
    characters: list[Character] = []
    episodes: list[Episode] = []


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def bible_path(title: str, root: Path = ROOT) -> Path:
    return root / "series" / slug(title) / "bible.json"


def load_bible(title: str, root: Path = ROOT) -> Bible | None:
    path = bible_path(title, root)
    if not path.exists():
        return None
    return Bible.model_validate_json(path.read_text(encoding="utf-8"))


def check_against_bible(package: ScriptPackage, bible: Bible) -> tuple[list[str], list[str]]:
    """Errors and warnings where an episode disagrees with its series so far."""
    errors, warnings = [], []
    known = {character.id: character for character in bible.characters}
    for character in package.characters:
        established = known.get(character.id)
        if established and established.visual_block != character.visual_block:
            errors.append(
                f"{character.name}'s visual_block differs from the series bible. Copy it from "
                f"series/{slug(bible.title)}/bible.json so the character looks the same as before."
            )
    number = package.series.episode_number
    recorded = {episode.number for episode in bible.episodes}
    expected = max(recorded, default=0) + 1
    if number not in recorded and number != expected:
        warnings.append(f"This is episode {number} but the next unrecorded episode is {expected}.")
    return errors, warnings


def record(package: ScriptPackage, bible: Bible | None) -> Bible:
    """The bible with this episode added (or replaced) and any new characters kept."""
    series = package.series
    if bible is None:
        bible = Bible(title=series.title, season_arc=series.season_arc)
    known = {character.id for character in bible.characters}
    bible.characters += [c for c in package.characters if c.id not in known]
    episode = Episode(number=series.episode_number, title=package.title,
                      summary=package.logline, cliffhanger=series.cliffhanger)
    bible.episodes = sorted(
        [e for e in bible.episodes if e.number != episode.number] + [episode],
        key=lambda e: e.number,
    )
    return bible
