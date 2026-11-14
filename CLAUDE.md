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

The page is also an app: its Create view asks Claude (on the viewer's own
plan) to write or revise scripts and stores them in the artifact's database,
collection `scripts`, as `{package, created, source}`. Those scripts are not in
this repo until imported. To import one: read the collection with the
ArtifactData tool, save its `package` as `scripts/<doc id>/package.json`, run
`uv run sensex render` on it (and `series record` for an episode), rebuild and
republish the page, then delete the database document so it is not listed
twice. When republishing, leave `capabilities` out so the stored ones
(`db`, `user`, `sample`) are kept.

## Working rules

- Run `uv run pytest` before committing code changes.
- Never post clips or anything else to social accounts without the user
  approving that specific item in the conversation.
- Only cut clips from footage the user owns or has permission to repost.
