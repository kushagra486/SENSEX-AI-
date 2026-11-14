---
name: trend-report
description: Scan what AI videos are trending right now and explain what is working. Use when asked for trends, what is hot, what to make next, or before writing any script if today's report does not exist.
---

# Trend report

1. Read `config/channel.yaml` so you know the niche, language, region and audience.
2. Run `uv run sensex trends` (add `--window month` for a wider view). It writes
   `data/trends/<date>.md` and `.json`. If a search failed, say which one.
3. Read the report. The numbers only cover YouTube search results, and regular
   search under-reports Shorts, so fill the gaps with web searches for what is
   trending this week on Instagram Reels, YouTube Shorts and TikTok in the
   channel's niche and language. Keep the links.
4. Append a `## What this means for us` section to the `.md` file covering:
   - **Storylines:** the 3 to 5 plot shapes pulling the most views, each with the videos that prove it.
   - **Formats:** which length and structure wins (series, long video, solo drama, short), by median views.
   - **Scenes and gameplay:** recurring visual set-pieces or game scenes.
   - **Hooks and titles:** how the top videos open and how they are titled.
   - **Reach:** posting patterns visible in the data (episode numbering, hashtags, language, upload rhythm of channels with several hits).
   - **Gaps:** what the audience clearly wants that few channels are making.
5. Give the user the five most useful findings in chat, with the file path.

Report only what the data or a linked source supports. A pattern seen in one video is an anecdote; say so.
