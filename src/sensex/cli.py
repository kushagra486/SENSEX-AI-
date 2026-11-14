"""Command line: `sensex trends`, `sensex check`, `sensex render`, `sensex clips`."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from sensex.clips import analyze as clip_analyze
from sensex.clips import cut as clip_cut
from sensex.config import ROOT, load_channel, load_tools
from sensex.script.package import ScriptPackage, budget, check
from sensex.script import assemble as script_assemble
from sensex.script import series as script_series
from sensex.script.render import episode_prompt, render
from sensex import site as site_builder
from sensex.generate import huggingface
from sensex.generate import kaggle as kaggle_runner
from sensex.generate import shots as generate_shots
from sensex.trends import analyze, sources


NOTES_HEADING = "## What this means for us"


def run_trends(args: argparse.Namespace) -> int:
    config = load_channel()
    window = args.window or config.scan.window
    videos: list[dict] = []
    shorts: list[dict] = []
    errors: list[str] = []
    for query in config.queries:
        for short, found in ((False, videos), (True, shorts)):
            print(f"Scanning YouTube{' short videos' if short else ''}: {query}", file=sys.stderr)
            try:
                found += sources.youtube_top_videos(
                    query, window, config.scan.results_per_query, short=short)
            except Exception as error:  # one failed search must not lose the others
                errors.append(f"{query}{' (short videos)' if short else ''}: {error}")
    try:
        trending = sources.google_trending_searches(config.channel.region)
    except Exception as error:
        trending = []
        errors.append(f"Google trending searches: {error}")

    report = {
        "date": date.today().isoformat(),
        "niche": config.channel.niche,
        "region": config.channel.region,
        "window": window,
        "errors": errors,
        "analysis": analyze.analyze(videos),
        "shorts_analysis": analyze.analyze(shorts),
        "trending_searches": trending,
    }
    out_dir = ROOT / "data" / "trends"
    out_dir.mkdir(parents=True, exist_ok=True)
    earlier = sorted(path for path in out_dir.glob("*.json") if path.stem < report["date"])
    if earlier:
        previous = json.loads(earlier[-1].read_text(encoding="utf-8"))
        report["compared_with"] = previous["date"]
        report["rising_words"] = analyze.rising_words(report["analysis"], previous["analysis"])
    json_path = out_dir / f"{report['date']}.json"
    md_path = out_dir / f"{report['date']}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # Keep the written analysis from an earlier run today; only the numbers are regenerated.
    notes = ""
    if md_path.exists():
        existing = md_path.read_text(encoding="utf-8")
        if NOTES_HEADING in existing:
            notes = "\n" + existing[existing.index(NOTES_HEADING):]
    md_path.write_text(analyze.to_markdown(report) + notes, encoding="utf-8")
    print(f"Wrote {md_path.relative_to(ROOT)} and {json_path.relative_to(ROOT)}")
    for error in errors:
        print(f"FAILED: {error}", file=sys.stderr)
    return 1 if not videos else 0


def _load_package(path: Path) -> ScriptPackage | None:
    try:
        return ScriptPackage.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        print(f"{path} is not a valid script package:")
        for issue in error.errors():
            print(f"  ERROR {'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}")
        return None


def run_check(args: argparse.Namespace) -> int:
    package = _load_package(args.package)
    if package is None:
        return 1
    tools = load_tools()
    result = check(package, tools)
    if package.series:
        bible = script_series.load_bible(package.series.title)
        if bible:
            errors, warnings = script_series.check_against_bible(package, bible)
            result.errors += errors
            result.warnings += warnings
    for message in result.errors:
        print(f"  ERROR {message}")
    for message in result.warnings:
        print(f"  WARNING {message}")
    spend = budget(package, tools)
    print(f"{len(package.shots)} shots, {package.runtime_seconds:g}s, "
          f"{spend.days_needed} day(s) of free credits. "
          + ("OK" if result.ok else f"{len(result.errors)} error(s)"))
    return 0 if result.ok else 1


def run_render(args: argparse.Namespace) -> int:
    if run_check(args) != 0:
        print("Not rendered: fix the errors first.")
        return 1
    package = _load_package(args.package)
    out_path = args.package.with_name("script.md")
    out_path.write_text(render(package, load_tools()), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


def run_series_record(args: argparse.Namespace) -> int:
    if run_check(args) != 0:
        print("Not recorded: fix the errors first.")
        return 1
    package = _load_package(args.package)
    if package.series is None:
        print("Not a series episode: nothing to record.")
        return 1
    bible = script_series.record(package, script_series.load_bible(package.series.title))
    path = script_series.bible_path(package.series.title)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bible.model_dump_json(indent=2), encoding="utf-8")
    print(f"Recorded episode {package.series.episode_number} in {path.relative_to(ROOT)} "
          f"({len(bible.episodes)} episode(s), {len(bible.characters)} character(s)).")
    return 0


def run_assemble(args: argparse.Namespace) -> int:
    package = _load_package(args.folder / "package.json")
    if package is None:
        return 1
    try:
        final = script_assemble.assemble(package, args.folder)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"ERROR {error}")
        return 1
    print(f"Wrote {final}")
    return 0


def run_gen(args: argparse.Namespace) -> int:
    package = _load_package(args.folder / "package.json")
    if package is None:
        return 1
    shots = {shot.id: shot for shot in package.shots}
    wanted = args.shots or list(shots)
    unknown = [shot_id for shot_id in wanted if shot_id not in shots]
    if unknown:
        print(f"No such shot(s): {', '.join(unknown)}. This script has {', '.join(shots)}.")
        return 1
    for shot_id in wanted:
        try:
            notes = generate_shots.generate_shot(
                package, shots[shot_id], args.folder, redo=args.redo,
                video=not args.voice_only, voice=not args.skip_voice)
        except huggingface.GenerationError as error:
            print(f"{shot_id}: FAILED. {error}")
            print("Files made so far are kept; run the same command again to continue.")
            return 1
        print(f"{shot_id}: " + ("; ".join(notes) or "nothing to do"))
    return 0


def run_kaggle_start(args: argparse.Namespace) -> int:
    package = _load_package(args.folder / "package.json")
    if package is None:
        return 1
    known = [shot.id for shot in package.shots]
    wanted = args.shots or [s for s in known if not (args.folder / "clips" / f"{s}.mp4").exists()]
    unknown = [shot_id for shot_id in wanted if shot_id not in known]
    if unknown:
        print(f"No such shot(s): {', '.join(unknown)}. This script has {', '.join(known)}.")
        return 1
    if not wanted:
        print("Every shot already has a clip. Name shots to redo them.")
        return 0
    try:
        record = kaggle_runner.start(package, args.folder, wanted)
    except kaggle_runner.KaggleError as error:
        print(f"ERROR {error}")
        return 1
    print(f"Started on Kaggle: {len(wanted)} shot(s) ({', '.join(wanted)}). {record['url']}")
    print(f"Collect the clips later with: sensex kaggle collect {args.folder}")
    return 0


def run_kaggle_collect(args: argparse.Namespace) -> int:
    try:
        result = kaggle_runner.collect(args.folder)
    except kaggle_runner.KaggleError as error:
        print(f"ERROR {error}")
        return 1
    for line in result["progress"]:
        print(f"  {line}")
    if not result["finished"]:
        for line in result["trouble"]:
            print(f"  PROBLEM {line[:300]}")
        waiting = " It is waiting in Kaggle's queue for a free GPU." if result["state"] == "queued" else ""
        print(f"Not finished yet (Kaggle says: {result['state']}).{waiting} Run this again in a few minutes.")
        return 2
    failed = {k: v for k, v in result["results"].items() if not v.get("ok")}
    print(f"Finished in {result['total_seconds']}s. Saved clips: {', '.join(result['saved']) or 'none'}.")
    for shot_id, outcome in failed.items():
        print(f"  FAILED {shot_id}: {outcome.get('error')}")
    return 1 if failed else 0


def run_prompt(args: argparse.Namespace) -> int:
    package = _load_package(args.package)
    if package is None:
        return 1
    print(episode_prompt(package))
    return 0


def run_site(args: argparse.Namespace) -> int:
    path = site_builder.build()
    print(f"Wrote {path.relative_to(ROOT)}")
    return 0


def _clip_dir(video: Path) -> Path:
    return ROOT / "clips" / video.stem


def run_clips_find(args: argparse.Namespace) -> int:
    if not args.video.exists():
        print(f"No such video: {args.video}")
        return 1
    print("Measuring audio, scene cuts and speech. Long videos take a while.", file=sys.stderr)
    analysis = clip_analyze.analyze_video(args.video, args.model, args.min, args.max)
    out_dir = _clip_dir(args.video)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "analysis.json"
    path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{analysis['duration_seconds']:g}s video, speech: {'yes' if analysis['has_speech'] else 'no'}, "
          f"{analysis['scene_cuts']} scene cuts, {len(analysis['candidates'])} candidate moments.")
    for row in analysis["candidates"]:
        print(f"  {row['start']:>8.1f}-{row['end']:<8.1f} score {row['score']:>5}  {row['text'][:80]}")
    print(f"Wrote {path.relative_to(ROOT)}")
    return 0


def run_clips_cut(args: argparse.Namespace) -> int:
    try:
        plan = clip_cut.ClipPlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
    except ValidationError as error:
        print(f"{args.plan} is not a valid clip plan:")
        for issue in error.errors():
            print(f"  ERROR {'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}")
        return 1
    out_dir = _clip_dir(args.video)
    analysis_path = out_dir / "analysis.json"
    transcript = []
    if analysis_path.exists():
        transcript = json.loads(analysis_path.read_text(encoding="utf-8"))["transcript"]
    outputs = {}
    for clip in plan.clips:
        outputs[clip.id] = clip_cut.cut_clip(args.video, clip, transcript, out_dir)
        print(f"Cut {outputs[clip.id].relative_to(ROOT)}")
    sheet = out_dir / "review.md"
    sheet.write_text(clip_cut.review_sheet(plan, outputs), encoding="utf-8")
    print(f"Wrote {sheet.relative_to(ROOT)}. Nothing has been posted.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="sensex", description="Trend research and AI video scripts.")
    commands = parser.add_subparsers(dest="command", required=True)

    trends = commands.add_parser("trends", help="Scan what is trending and write a report.")
    trends.add_argument("--window", choices=["week", "month"])
    trends.set_defaults(run=run_trends)

    for name, run, text in (("check", run_check, "Check a script package against the tool limits."),
                            ("render", run_render, "Check a package, then write script.md beside it.")):
        command = commands.add_parser(name, help=text)
        command.add_argument("package", type=Path)
        command.set_defaults(run=run)

    series = commands.add_parser("series", help="Keep a series consistent across episodes.")
    series_commands = series.add_subparsers(dest="series_command", required=True)
    record = series_commands.add_parser("record", help="Add an episode to its series bible.")
    record.add_argument("package", type=Path)
    record.set_defaults(run=run_series_record)

    assemble = commands.add_parser("assemble", help="Join generated clips into the final video.")
    assemble.add_argument("folder", type=Path, help="Script folder holding package.json and clips/.")
    assemble.set_defaults(run=run_assemble)

    gen = commands.add_parser("gen", help="Generate clips for a script on free Hugging Face Spaces.")
    gen.add_argument("folder", type=Path, help="Script folder holding package.json.")
    gen.add_argument("shots", nargs="*", help="Shot ids to generate; all shots if omitted.")
    gen.add_argument("--redo", action="store_true", help="Replace files that already exist.")
    gen.add_argument("--voice-only", action="store_true", help="Only make the spoken lines.")
    gen.add_argument("--skip-voice", action="store_true", help="Only make frames and clips.")
    gen.set_defaults(run=run_gen)

    kaggle = commands.add_parser("kaggle", help="Generate clips on Kaggle's free GPUs.")
    kaggle_commands = kaggle.add_subparsers(dest="kaggle_command", required=True)
    k_start = kaggle_commands.add_parser("start", help="Start generating clips for a script.")
    k_start.add_argument("folder", type=Path)
    k_start.add_argument("shots", nargs="*", help="Shot ids; every shot without a clip if omitted.")
    k_start.set_defaults(run=run_kaggle_start)
    k_collect = kaggle_commands.add_parser("collect", help="Download the clips once the run finishes.")
    k_collect.add_argument("folder", type=Path)
    k_collect.set_defaults(run=run_kaggle_collect)

    prompt = commands.add_parser("prompt", help="Print one prompt holding a whole episode.")
    prompt.add_argument("package", type=Path)
    prompt.set_defaults(run=run_prompt)

    site = commands.add_parser("site", help="Build the web view of scripts, series and trends.")
    site.set_defaults(run=run_site)

    clips = commands.add_parser("clips", help="Find and cut short clips from a video you own.")
    clip_commands = clips.add_subparsers(dest="clip_command", required=True)
    find = clip_commands.add_parser("find", help="Shortlist the best moments in a video.")
    find.add_argument("video", type=Path)
    find.add_argument("--model", default="small", help="Speech model: tiny, base, small, medium.")
    find.add_argument("--min", type=float, default=20.0, help="Shortest clip in seconds.")
    find.add_argument("--max", type=float, default=60.0, help="Longest clip in seconds.")
    find.set_defaults(run=run_clips_find)
    cut = clip_commands.add_parser("cut", help="Cut the clips listed in a plan file.")
    cut.add_argument("video", type=Path)
    cut.add_argument("plan", type=Path)
    cut.set_defaults(run=run_clips_cut)

    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
