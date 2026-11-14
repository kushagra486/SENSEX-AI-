# SENSEX-AI

Finds out what AI videos are trending, then writes complete script packages
whose prompts you paste into AI video tools.

It runs inside Claude Code, so it uses your Claude subscription and needs no
API keys.

## How to use it

Open this folder in Claude Code and ask in plain words:

- **"What's trending?"** scans YouTube and Google trending searches for your
  niche and writes a report to `data/trends/`.
- **"Write me a short / solo drama / series episode / long video"** pitches
  three ideas from the latest trends, then writes the one you pick to
  `scripts/<date>-<name>/script.md`.
- **"Write the next episode of <series>"** continues a series with the same
  characters.
- **"Assemble <script folder>"** joins the clips you generated into the
  finished video. Save each clip as `scripts/<folder>/clips/S1.mp4`,
  `S2.mp4`... (and optional voiceovers as `scripts/<folder>/audio/S2.mp3`),
  and it writes `final.mp4` with the on-screen text added.
- **"Cut clips from media/<file>"** finds the best moments in a video you own,
  and cuts them into vertical 1080x1920 clips with captions in
  `clips/<name>/`, with a review sheet. Only use footage you made or have
  permission to repost.

Each `script.md` contains the story, character sheets with reference-image
prompts, every shot as a paste-ready prompt tagged with the tool to use, an
edit timeline, a credit budget, and a title, caption and hashtags.
See `examples/script.md`.

## The web app

Sensex Studio: https://claude.ai/artifact/7fo36vcfSafnu75euxAWuN (private to
you unless you share it). It runs on your Claude plan; there is no API key.

- **Create:** choose a format or "next episode of" a series, add an idea or
  leave it empty, and Claude writes the script from the latest trend scan. The
  page checks clip lengths and daily credits, asks Claude once to fix anything
  that breaks them, and saves the script.
- **Scripts:** every script, with a copy button on each prompt, and a box to
  ask for a change, which saves a new version.
- **Series** and **Trends:** the series bibles and the latest trend report.

Two things still happen in a Claude Code session, not in the app: running a
new trend scan (the page cannot reach YouTube) and cutting or assembling
video. Scripts written in the app are stored with the page; a session can
import them into this repo. `uv run sensex site` rebuilds the page to
`site/index.html`.

## What you need to add

| What | Where | Needed for |
|---|---|---|
| Your niche, language, country, audience | `config/channel.yaml` | Every report and script |
| Your search terms | `config/channel.yaml`, under `queries` | The trend scan |
| Real limits of your video tools | `config/tools.yaml` | The credit budget |
| Character reference images | Make them from the prompts in each `script.md`, keep them with the script | Consistent characters |
| Generated clips, named by shot | `scripts/<folder>/clips/` | Assembling the video |
| Voiceover files (optional) | `scripts/<folder>/audio/` | Tools that make silent clips |
| A video you own | `media/` | Cutting clips |
| Instagram and YouTube connected in Metricool | Metricool, Connections | Posting |

## Set it up for your channel

- `config/channel.yaml`: your niche, language, country, audience, and the
  searches the trend scan runs.
- `config/tools.yaml`: the video tools you use, their clip length limit and
  daily free credits. The shipped numbers are approximate; correct them from
  each tool's own page.

## What the checker enforces

Every script is checked before it is rendered:

- no shot is longer than its tool can generate
- each character's description is pasted word for word into every prompt they
  appear in, so they look the same across clips
- the shots add up to the target runtime
- the whole video can be generated within the free daily credits
- a series episode uses the same character descriptions as its series bible
  (`series/<name>/bible.json`)

It also warns about weak pacing: a slow opening shot, an opening with no text
or spoken line, long average shots, and long stretches with nobody speaking.

## Commands

```
uv run sensex trends [--window week|month]
uv run sensex check scripts/<folder>/package.json
uv run sensex render scripts/<folder>/package.json
uv run sensex series record scripts/<folder>/package.json
uv run sensex gen scripts/<folder> [shot ids] [--voice-only | --skip-voice] [--redo]
uv run sensex assemble scripts/<folder>
uv run sensex clips find media/<file> [--min 20 --max 60]
uv run sensex clips cut media/<file> clips/<name>/plan.json
uv run pytest
```

## Generating the video for free (Hugging Face)

`uv run sensex gen scripts/<folder> [S1 S2 ...]` makes, for each shot:

- a reference image per character (once per series, in `series/<name>/refs/`)
- a still first frame, edited from the reference so the character looks the
  same in every shot
- a silent clip of up to 5 seconds, saved as `clips/S1.mp4`
- the spoken line as `audio/S1.wav`, in a voice cloned from that speaker's
  first line (`series/<name>/voices/`)

Then `assemble` joins everything. It all runs on public Hugging Face Spaces
and needs your Hugging Face token: in a Claude cloud session, saved as a
network secret for each Space host (image, character editor, video, voice);
on your own computer, as the `HF_TOKEN` environment variable.

The free daily GPU allowance is small. On the first real run it covered two
clips with their frames and one character reference, then refused until the
next day. Hugging Face PRO raises it to 40 minutes a day. The command skips
files that already exist, so run it again each day to continue.

Other routes: ElevenLabs (connected) can do voices, music and images but its
video generation needs a paid plan; the free websites (Dreamina, Kling, Google
Flow) have the most free clips but only by pasting prompts by hand.

## Posting

Clips are never posted automatically. After you approve a clip, posting goes
through Metricool, which needs your Instagram and YouTube accounts connected
there. Until then, upload the mp4 files yourself.
