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
- **"Cut clips from media/<file>"** finds the best moments in a video you own,
  and cuts them into vertical 1080x1920 clips with captions in
  `clips/<name>/`, with a review sheet. Only use footage you made or have
  permission to repost.

Each `script.md` contains the story, character sheets with reference-image
prompts, every shot as a paste-ready prompt tagged with the tool to use, an
edit timeline, a credit budget, and a title, caption and hashtags.
See `examples/script.md`.

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

## Commands

```
uv run sensex trends [--window week|month]
uv run sensex check scripts/<folder>/package.json
uv run sensex render scripts/<folder>/package.json
uv run sensex clips find media/<file> [--min 20 --max 60]
uv run sensex clips cut media/<file> clips/<name>/plan.json
uv run pytest
```

## Posting

Clips are never posted automatically. After you approve a clip, posting goes
through Metricool, which needs your Instagram and YouTube accounts connected
there. Until then, upload the mp4 files yourself.
