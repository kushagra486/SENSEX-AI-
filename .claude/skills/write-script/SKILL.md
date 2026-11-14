---
name: write-script
description: Write a complete, paste-ready script package for an AI-generated video (short, solo drama, series episode or long video) based on current trends. Use when asked for a script, a video idea turned into shots, a new series, or the next episode.
---

# Write a script package

The output is `scripts/<date>-<slug>/package.json` plus a rendered `script.md`
whose prompts get pasted into AI video tools. `examples/package.json` shows the
exact shape; `src/sensex/script/package.py` defines every field.

## Steps

1. Read `config/channel.yaml`, `config/tools.yaml` and the newest report in
   `data/trends/`. If the newest report is more than 3 days old, run the
   trend-report skill first.
2. If the user did not choose a format, pick the one the report favours and say why.
3. For a series: read `series/<slug>/bible.json` if it exists. It holds the
   fixed characters and a log of every episode. Copy the characters from it
   unchanged (same `id`, same `visual_block`), continue the `season_arc`, pick
   up from the last episode's cliffhanger, and summarise it in `previously`.
   The check fails if a character's look differs from the bible.
4. Pitch three ideas in chat, one line each, with the trend each draws on and
   its twist. Let the user pick, unless they asked you to choose.
5. Write `package.json`.
6. Run `uv run sensex render scripts/<date>-<slug>/package.json`. Fix every
   error and re-run until it passes. Read the warnings and fix the ones that matter.
7. For a series episode, run `uv run sensex series record <package.json>` so
   the bible knows this episode exists.
8. Tell the user the file path, the runtime, and how many days of credits it needs.

## After the user has generated the clips

They save each clip in `scripts/<folder>/clips/` named after its shot
(`S1.mp4`, `S2.mp4`...), and optional voiceover files in
`scripts/<folder>/audio/` with the same names. Then run
`uv run sensex assemble scripts/<folder>`. It joins the shots in order at the
scripted lengths, adds the on-screen text, and writes `final.mp4`. If clips
are missing it names them. Music and transitions other than hard cuts are not
added; say so.

## Originality

Trends are for learning what works, never for copying. Take the pattern (a
hidden-identity reveal, a cliffhanger rhythm, a pacing style) and build a new
premise, world and characters on it. Never reuse another video's title,
characters, dialogue or distinctive plot, and never use real people, existing
franchises or copyrighted characters. `original_twist` must name what is ours.

## Writing rules

- **Hook:** the first shot is 2 to 4 seconds and shows the strangest or most
  tense image of the video. No titles, no slow establishing shots.
- **Variants:** give two other openings in `hook_variants` and two other titles
  in `title_variants`. Each must be a different angle on the same video, not a
  rewording, so posting them tells us which angle the audience prefers.
- **Characters:** write each `visual_block` once, as concrete as possible (age,
  build, hair, face mark, exact clothing and colours), then paste it word for
  word into every prompt the character appears in. Keep casts small: 2 or 3
  characters for anything under 3 minutes.
- **Prompts:** every prompt stands alone. The video tool has no memory, so
  repeat the aspect ratio, visual style, location, time of day and lighting in
  each one. One action and one camera move per shot. Put spoken lines in quotes
  inside the prompt for tools that generate audio.
- **Tool choice:** spend the scarce high-quality clips (tools with audio and few
  daily credits) on dialogue and the key emotional beats. Put silent action,
  inserts and atmosphere on the high-volume tool, with voiceover instead of
  on-screen dialogue.
- **Length:** no shot may exceed its tool's `max_clip_seconds`. Split longer
  beats into several shots that cut on movement.
- **Ending:** series episodes end on a cliffhanger that is a new question, not
  a pause. Solo dramas and long videos resolve the main question and leave one
  image to remember.
- **Long videos:** plan them as chapters of 60 to 90 seconds, each with its own
  small hook, and check the credit budget early; they take several days to generate.
- **Posting pack:** title and caption follow the habits in the trend report, in
  the channel's language.
