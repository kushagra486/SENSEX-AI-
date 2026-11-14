"""Renders a script package as a Markdown document with copy-paste prompts."""

from sensex.config import ToolsConfig
from sensex.script.package import ScriptPackage, budget


def _clock(seconds: float) -> str:
    whole = int(round(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def _code(text: str) -> str:
    return f"```text\n{text.strip()}\n```"


def render(package: ScriptPackage, tools: ToolsConfig) -> str:
    out: list[str] = [f"# {package.title}", f"*{package.logline}*"]
    out.append(
        f"**Format:** {package.format.replace('_', ' ')} · **Platform:** {package.platform} · "
        f"**Aspect:** {package.aspect_ratio} · **Runtime:** {_clock(package.runtime_seconds)} "
        f"({len(package.shots)} shots)"
    )

    out.append("## Why this video\n\n" + "\n".join(f"- Trend: {item}" for item in package.trend_basis)
               + f"\n- Our twist: {package.original_twist}")

    if package.series:
        series = package.series
        lines = [f"## Series: {series.title}, episode {series.episode_number}",
                 f"**Season arc:** {series.season_arc}"]
        if series.previously:
            lines.append(f"**Previously:** {series.previously}")
        lines.append(f"**Cliffhanger:** {series.cliffhanger}")
        out.append("\n\n".join(lines))

    story = ["## Story", f"**Opening hook (first 3 seconds):** {package.story.opening_hook}"]
    story += [f"**{act.name}:** {act.summary}" for act in package.story.acts]
    story.append(f"**Ending:** {package.story.ending}")
    out.append("\n\n".join(story))

    spend = budget(package, tools)
    rows = ["| Tool | Clips | Credits | Days of free credits |", "|---|---|---|---|"]
    for name, clips in spend.clips.items():
        rows.append(f"| {tools.tools[name].label} | {clips} | {spend.credits[name]:g} | {spend.days[name]} |")
    out.append("## Credit budget\n\n" + "\n".join(rows)
               + f"\n\nAll clips can be generated in **{spend.days_needed} day(s)**.")

    out.append("## Characters\n\nMake each reference image first, then attach it to every clip "
               "the character appears in.")
    for character in package.characters:
        out.append(
            f"### {character.name} ({character.role})\n\n"
            f"- **Type:** {character.archetype}\n- **Personality:** {character.personality}\n"
            f"- **Voice:** {character.voice}\n\n**Reference image prompt:**\n\n"
            f"{_code(character.reference_image_prompt)}"
        )

    names = {character.id: character.name for character in package.characters}
    out.append("## Shots\n\nGenerate in this order. Paste each prompt exactly as written.")
    start = 0.0
    for shot in package.shots:
        end = start + shot.duration_seconds
        label = tools.tools[shot.tool].label if shot.tool in tools.tools else shot.tool
        lines = [f"### {shot.id} · {_clock(start)}-{_clock(end)} · {shot.duration_seconds:g}s · {label}",
                 f"*{shot.act}*" + (f" · with {', '.join(names.get(c, c) for c in shot.characters)}"
                                    if shot.characters else ""),
                 _code(shot.prompt)]
        for title, value in (("Dialogue", shot.dialogue), ("Voiceover", shot.voiceover),
                             ("Sound", shot.sound), ("On-screen text", shot.on_screen_text)):
            if value:
                lines.append(f"- **{title}:** {value}")
        out.append("\n\n".join(lines))
        start = end

    rows = ["| Time | Shot | Transition in | On-screen text | Audio |", "|---|---|---|---|---|"]
    start = 0.0
    for shot in package.shots:
        audio = " / ".join(part for part in (shot.dialogue, shot.voiceover, shot.sound) if part)
        cells = [f"{_clock(start)}-{_clock(start + shot.duration_seconds)}", shot.id,
                 shot.transition, shot.on_screen_text or "-", audio or "-"]
        rows.append("| " + " | ".join(cell.replace("|", "/") for cell in cells) + " |")
        start += shot.duration_seconds
    out.append("## Edit timeline\n\n" + "\n".join(rows))

    posting = package.posting
    out.append(
        f"## Posting pack\n\n**Title:** {posting.title}\n\n**Caption:** {posting.caption}\n\n"
        f"**Hashtags:** {' '.join(posting.hashtags)}\n\n**Thumbnail prompt:**\n\n"
        f"{_code(posting.thumbnail_prompt)}"
    )
    return "\n\n".join(out) + "\n"
