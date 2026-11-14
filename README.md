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

## The web view

Everything is also visible on one page, Sensex Studio:
https://claude.ai/artifact/7fo36vcfSafnu75euxAWuN (private to you unless you
share it). It shows every script with a copy button on each prompt, the series
bibles, and the latest trend report. It is a viewer: you ask for new scripts
in the Claude session, and Claude rebuilds and republishes the page.
`uv run sensex site` builds it to `site/index.html`.

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
uv run sensex assemble scripts/<folder>
uv run sensex clips find media/<file> [--min 20 --max 60]
uv run sensex clips cut media/<file> clips/<name>/plan.json
uv run pytest
```

## Posting

Clips are never posted automatically. After you approve a clip, posting goes
through Metricool, which needs your Instagram and YouTube accounts connected
there. Until then, upload the mp4 files yourself.
