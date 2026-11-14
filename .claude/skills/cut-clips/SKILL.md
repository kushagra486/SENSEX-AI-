---
name: cut-clips
description: Find the best moments in a long video or stream recording the user provides and cut them into vertical clips for YouTube Shorts and Instagram Reels. Use when asked to clip, cut highlights, or turn a video into shorts.
---

# Cut clips from a video

## Before anything else: rights

Ask who owns the footage unless the user already said. Only cut footage the
user made themselves or has permission to repost. Clips of other people's
streams or videos get accounts struck for copyright, so do not cut or post
those; say why. The answer goes in the plan's `rights` field.

## Steps

1. Put the video in `media/` (it is not committed). Run
   `uv run sensex clips find media/<file>`. Add `--min` / `--max` to change the
   clip length range (default 20 to 60 seconds). It writes
   `clips/<name>/analysis.json` with a transcript and a ranked shortlist.
2. Choose the clips yourself. The shortlist ranks by loudness, cutting pace and
   speech density, which finds energetic moments but cannot judge meaning. Read
   the transcript and pick moments that:
   - open with a line or image that makes sense with no context
   - contain one complete beat: a joke with its punchline, a claim with its
     proof, a fail and the reaction
   - end on the payoff, not mid-sentence
   You may adjust start and end times; keep them on sentence boundaries from
   the transcript. Check the newest report in `data/trends/` for which topics
   and title habits are working, and prefer moments that match.
3. Write `clips/<name>/plan.json`:
   ```json
   {"rights": "My own gameplay recording from 12 Nov.",
    "clips": [{"id": "clutch-win", "start": 754.2, "end": 791.0,
               "title": "...", "caption": "...", "hashtags": ["#shorts"],
               "why": "Why this moment stands on its own.",
               "layout": "blur", "captions": true}]}
   ```
   `layout` is `blur` (whole picture over a blurred background; right for
   gameplay and wide shots) or `crop` (fills the screen, cuts off the sides;
   right for a centred face).
4. Run `uv run sensex clips cut media/<file> clips/<name>/plan.json`. It writes
   one 1080x1920 mp4 per clip with burned-in captions, plus `review.md`.
5. Show the user `review.md` and the clip files. Stop here.

## Posting

Never post without the user approving that specific clip in this conversation.
An earlier "post them all" does not cover clips cut later.

Posting goes through the Metricool connector, which needs the user's Instagram
and YouTube accounts connected in Metricool and each clip at a public link.
If either is missing, say what is missing and hand over the files for manual
upload instead.
