"""Renders a script package as a Markdown document with copy-paste prompts."""

from sensex.config import ToolsConfig
from sensex.script.package import ScriptPackage, budget


def _clock(seconds: float) -> str:
    whole = int(round(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def _code(text: str) -> str:
    return f"```text\n{text.strip()}\n```"


def shared_style(package: ScriptPackage) -> str:
    """The opening sentences every shot prompt has in common: the look of the whole video."""
    prompts = [shot.prompt for shot in package.shots]
    prefix = prompts[0]
    for prompt in prompts[1:]:
        while not prompt.startswith(prefix):
            prefix = prefix[:-1]
    cut = prefix.rfind(". ")
    return prefix[: cut + 1].strip() if cut > 0 else ""


def episode_prompt(package: ScriptPackage) -> str:
    """One prompt holding the whole episode: look, characters, every shot, sound and editing."""
    style = shared_style(package)
    looks = {character.visual_block: character.name for character in package.characters}
    lines = [
        f'Create one {_clock(package.runtime_seconds)} video in {package.aspect_ratio} format: "{package.title}".',
        f"STORY: {package.logline}",
    ]
    if package.series:
        lines.append(f"This is episode {package.series.episode_number} of the series "
                     f'"{package.series.title}". It must end on this cliffhanger: {package.series.cliffhanger}')
    if style:
        lines.append(f"LOOK (identical in every shot): {style}")
    lines.append("CHARACTERS (each must look exactly the same in every shot they appear in):")
    for character in package.characters:
        lines.append(f"- {character.visual_block}. Role: {character.role}. "
                     f"Personality: {character.personality}. Voice: {character.voice}.")
    lines.append(f"SHOTS, in order ({len(package.shots)} shots; keep each to its exact length):")
    start = 0.0
    for number, shot in enumerate(package.shots, 1):
        action = shot.prompt[len(style):].strip() if style and shot.prompt.startswith(style) else shot.prompt
        for look, name in looks.items():
            action = action.replace(look, name)
        end = start + shot.duration_seconds
        parts = [f"{number}. [{_clock(start)}-{_clock(end)}, {shot.duration_seconds:g}s] {action}"]
        if shot.dialogue:
            parts.append(f"Spoken on screen, lips in sync: {shot.dialogue}")
        if shot.voiceover:
            parts.append(f"Voiceover (not lip-synced): {shot.voiceover}")
        if shot.sound:
            parts.append(f"Sound: {shot.sound}.")
        if shot.on_screen_text:
            parts.append(f'On-screen caption: "{shot.on_screen_text}"')
        parts.append(f"Transition into this shot: {shot.transition}.")
        lines.append(" ".join(parts))
        start = end
    lines.append(
        "EDITING: Cut on action with no fades unless a shot says otherwise. Captions are bold white "
        "with a black outline in the upper third, shown for the whole shot they belong to; add no "
        "other text, logos or watermarks. Keep colour, lighting and character looks continuous from "
        "shot to shot. Voices sit above music and sound effects. End on the last shot's image, then "
        "cut to black."
    )
    return "\n\n".join(lines)


def render(package: ScriptPackage, tools: ToolsConfig) -> str:
    out: list[str] = [f"# {package.title}", f"*{package.logline}*"]
    out.append(
        f"**Format:** {package.format.replace('_', ' ')} · **Platform:** {package.platform} · "
        f"**Aspect:** {package.aspect_ratio} · **Runtime:** {_clock(package.runtime_seconds)} "
        f"({len(package.shots)} shots)"
    )

    out.append("## Whole-episode prompt\n\nEverything in one prompt, for a tool that makes a whole video "
               "from a single description. Tools that make one short clip at a time need the "
               "per-shot prompts further down instead.\n\n" + _code(episode_prompt(package)))

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
    story.append("**Other openings to test:**\n" + "\n".join(
        f"- {hook}" for hook in package.story.hook_variants))
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
        f"## Posting pack\n\n**Title:** {posting.title}\n\n**Other titles to test:**\n"
        + "\n".join(f"- {title}" for title in posting.title_variants)
        + f"\n\n**Caption:** {posting.caption}\n\n"
        f"**Hashtags:** {' '.join(posting.hashtags)}\n\n**Thumbnail prompt:**\n\n"
        f"{_code(posting.thumbnail_prompt)}"
    )
    return "\n\n".join(out) + "\n"
