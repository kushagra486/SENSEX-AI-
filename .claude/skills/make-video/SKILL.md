---
name: make-video
description: Generate the actual video for a script package: character reference images, a clip per shot, spoken lines, then the assembled final video. Use when asked to make, generate, render or produce the video or clips for a script.
---

# Make the video for a script

## What can generate what

| Route | Makes | Cost and limit | How |
|---|---|---|---|
| Hugging Face Spaces | Character reference images, a still per shot that keeps the character consistent, silent clips up to 5s (480x832), spoken lines in a consistent voice per speaker | Free. The account's daily GPU allowance covered about two clips plus their frames on 14 Nov 2026, then refused until the next day | `uv run sensex gen scripts/<folder> [shot ids]` |
| ElevenLabs connector | Voices, music, sound effects, images. Not video: video generation needs a paid ElevenLabs plan | Speech costs 1 credit per character; free generations are sometimes refused as busy | ElevenLabs tools; always run with `estimate_only` first and tell the user the cost |
| Free websites (Dreamina, Kling, Google Flow, Veo in Gemini) | The bulk of clips, some with sound | Free daily credits, website only | The user pastes prompts from Sensex Studio and saves clips as `scripts/<folder>/clips/<shot id>.mp4` |
| Canva connector | A whole short video from a storyboard | Uses the user's Canva AI limit | Needs the user's explicit yes to Canva's heads-up before every generation |

## Steps

1. Run `uv run sensex gen scripts/<folder>` for the shots wanted. It skips files
   that exist, so after a quota refusal run the same command again the next day.
   The first line a speaker says becomes their voice sample in
   `series/<name>/voices/`; character references go in `series/<name>/refs/`.
   Commit both: they are the series' identity.
2. Tell the user which shots are still missing and that they can fill them from
   the free websites.
3. When every shot has a clip, run `uv run sensex assemble scripts/<folder>`.
   It adds on-screen text and the voice files. There is no music step yet.
4. Send the user `final.mp4`. Never post it anywhere without their approval of
   that specific video.

A shot with two characters only keeps the first one consistent; say so if it matters.
