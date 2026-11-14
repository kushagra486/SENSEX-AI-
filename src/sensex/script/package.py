"""The script package: everything needed to generate and assemble one video.

`check` enforces the rules that make a package usable in the video tools:
clips fit each tool's length limit, characters stay consistent, and the
whole thing can be generated within the free daily credits.
"""

import math
from typing import Literal

from pydantic import BaseModel, Field

from sensex.config import ToolsConfig

Format = Literal["short", "solo_drama", "series_episode", "long_video"]

# Sensible total runtimes per format, in seconds. Outside the range is a warning.
RUNTIME_RANGE: dict[str, tuple[int, int]] = {
    "short": (15, 90),
    "solo_drama": (60, 240),
    "series_episode": (30, 240),
    "long_video": (300, 1800),
}
RUNTIME_TOLERANCE = 0.15
MAX_HOOK_SHOT_SECONDS = 4
MAX_AVERAGE_SHOT_SECONDS = 7
MAX_SILENT_STRETCH_SECONDS = 16


class Character(BaseModel):
    id: str
    name: str
    role: str = Field(description="protagonist, antagonist, mentor, comic relief...")
    archetype: str
    personality: str
    voice: str
    visual_block: str = Field(
        min_length=40,
        description="Exact appearance text, pasted unchanged into every prompt the character is in.",
    )
    reference_image_prompt: str


class Act(BaseModel):
    name: str
    summary: str


class Story(BaseModel):
    opening_hook: str = Field(min_length=10, description="What the viewer sees in the first 3 seconds.")
    hook_variants: list[str] = Field(
        min_length=2,
        description="Other openings for the same video, to post as tests against the main hook.",
    )
    acts: list[Act] = Field(min_length=1)
    ending: str = Field(min_length=10)


class Series(BaseModel):
    title: str
    episode_number: int = Field(ge=1)
    season_arc: str
    previously: str = ""
    cliffhanger: str = Field(min_length=10)


class Shot(BaseModel):
    id: str
    act: str
    duration_seconds: float = Field(gt=0)
    tool: str
    characters: list[str] = []
    prompt: str = Field(min_length=20)
    dialogue: str = ""
    voiceover: str = ""
    sound: str = ""
    on_screen_text: str = ""
    transition: str = "cut"


class Posting(BaseModel):
    title: str
    title_variants: list[str] = Field(min_length=2, description="Other titles to test.")
    caption: str
    hashtags: list[str]
    thumbnail_prompt: str


class ScriptPackage(BaseModel):
    format: Format
    title: str
    logline: str
    platform: str
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    target_runtime_seconds: float = Field(gt=0)
    trend_basis: list[str] = Field(min_length=1, description="The trends this draws on.")
    original_twist: str = Field(min_length=20, description="What makes it ours and not a copy.")
    series: Series | None = None
    characters: list[Character]
    story: Story
    shots: list[Shot] = Field(min_length=1)
    posting: Posting

    @property
    def runtime_seconds(self) -> float:
        return sum(shot.duration_seconds for shot in self.shots)


class Budget(BaseModel):
    clips: dict[str, int]
    credits: dict[str, float]
    days: dict[str, int]

    @property
    def days_needed(self) -> int:
        return max(self.days.values(), default=0)


def budget(package: ScriptPackage, tools: ToolsConfig) -> Budget:
    """Clips, credits and days of free credits needed per tool."""
    clips: dict[str, int] = {}
    for shot in package.shots:
        if shot.tool in tools.tools:
            clips[shot.tool] = clips.get(shot.tool, 0) + 1
    credits = {name: count * tools.tools[name].credits_per_clip for name, count in clips.items()}
    days = {name: math.ceil(used / tools.tools[name].daily_credits) for name, used in credits.items()}
    return Budget(clips=clips, credits=credits, days=days)


class CheckResult(BaseModel):
    errors: list[str] = []
    warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors


def check(package: ScriptPackage, tools: ToolsConfig) -> CheckResult:
    result = CheckResult()
    characters = {character.id: character for character in package.characters}

    if len(characters) != len(package.characters):
        result.errors.append("Two characters share the same id.")
    shot_ids = [shot.id for shot in package.shots]
    if len(set(shot_ids)) != len(shot_ids):
        result.errors.append("Two shots share the same id.")
    if package.format == "series_episode" and package.series is None:
        result.errors.append("A series episode needs the `series` section (arc and cliffhanger).")

    act_names = {act.name for act in package.story.acts}
    for shot in package.shots:
        if shot.act not in act_names:
            result.errors.append(f"Shot {shot.id}: act '{shot.act}' is not in the story.")
        tool = tools.tools.get(shot.tool)
        if tool is None:
            result.errors.append(
                f"Shot {shot.id}: unknown tool '{shot.tool}'. Known: {', '.join(tools.tools)}."
            )
            continue
        if shot.duration_seconds > tool.max_clip_seconds:
            result.errors.append(
                f"Shot {shot.id}: {shot.duration_seconds:g}s is longer than {tool.label}'s "
                f"{tool.max_clip_seconds:g}s clip limit. Split it."
            )
        if shot.dialogue and not tool.has_audio:
            result.warnings.append(
                f"Shot {shot.id}: has dialogue but {tool.label} makes silent clips; "
                "the line must be voiced separately and lip movement will not match."
            )
        for character_id in shot.characters:
            character = characters.get(character_id)
            if character is None:
                result.errors.append(f"Shot {shot.id}: unknown character '{character_id}'.")
            elif character.visual_block not in shot.prompt:
                result.errors.append(
                    f"Shot {shot.id}: prompt must contain {character.name}'s visual_block word "
                    "for word, or the character will look different in this clip."
                )

    first = package.shots[0]
    if first.duration_seconds > MAX_HOOK_SHOT_SECONDS:
        result.warnings.append(
            f"Shot {first.id}: the opening shot is {first.duration_seconds:g}s. Viewers decide "
            f"in the first few seconds; keep it to {MAX_HOOK_SHOT_SECONDS}s or less."
        )

    used = {character_id for shot in package.shots for character_id in shot.characters}
    for character_id in characters.keys() - used:
        result.warnings.append(f"Character '{character_id}' never appears in a shot.")

    runtime = package.runtime_seconds
    target = package.target_runtime_seconds
    if abs(runtime - target) > target * RUNTIME_TOLERANCE:
        result.errors.append(
            f"Shots add up to {runtime:g}s but the target runtime is {target:g}s "
            f"(allowed drift {RUNTIME_TOLERANCE:.0%})."
        )
    low, high = RUNTIME_RANGE[package.format]
    if not low <= runtime <= high:
        result.warnings.append(
            f"{runtime:g}s is outside the usual {low}-{high}s range for a {package.format}."
        )

    if not (first.on_screen_text or first.dialogue or first.voiceover):
        result.warnings.append(
            f"Shot {first.id}: the opening has no on-screen text or spoken line. Many viewers "
            "watch muted and need a reason to stay in the first seconds."
        )
    if runtime <= 90 and runtime / len(package.shots) > MAX_AVERAGE_SHOT_SECONDS:
        result.warnings.append(
            f"Average shot is {runtime / len(package.shots):.1f}s. Short videos hold attention "
            f"better with a new image every {MAX_AVERAGE_SHOT_SECONDS}s or less."
        )
    quiet = longest = 0.0
    for shot in package.shots:
        quiet = 0.0 if (shot.dialogue or shot.voiceover) else quiet + shot.duration_seconds
        longest = max(longest, quiet)
    if longest > MAX_SILENT_STRETCH_SECONDS:
        result.warnings.append(
            f"{longest:g}s pass with no dialogue or voiceover. Add a line or shorten the stretch."
        )

    days = budget(package, tools).days_needed
    if days > tools.max_days_per_video:
        result.errors.append(
            f"Needs {days} days of free credits; the limit is {tools.max_days_per_video}. "
            "Use fewer shots or move shots to a tool with more daily credits."
        )
    return result
