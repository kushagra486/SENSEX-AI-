# SENSEX-AI

Trend research, script packages, and clip cutting for AI-generated videos.
See `README.md` for what each command does.

## Keep the web view current

The project has a web view (Sensex Studio) published as a Claude artifact:
https://claude.ai/artifact/7fo36vcfSafnu75euxAWuN

After any change to `scripts/`, `series/` or `data/trends/`, run
`uv run sensex site` and publish `site/index.html` to that artifact (pass the
link as `url` in a new session so the address stays the same). Tell the user
the page is updated.

## Working rules

- Run `uv run pytest` before committing code changes.
- Never post clips or anything else to social accounts without the user
  approving that specific item in the conversation.
- Only cut clips from footage the user owns or has permission to repost.
