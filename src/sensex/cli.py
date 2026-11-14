"""Command line: `sensex trends`, `sensex check`, `sensex render`."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from sensex.config import ROOT, load_channel, load_tools
from sensex.script.package import ScriptPackage, budget, check
from sensex.script.render import render
from sensex.trends import analyze, sources


def run_trends(args: argparse.Namespace) -> int:
    config = load_channel()
    window = args.window or config.scan.window
    videos: list[dict] = []
    errors: list[str] = []
    for query in config.queries:
        print(f"Scanning YouTube: {query}", file=sys.stderr)
        try:
            videos += sources.youtube_top_videos(query, window, config.scan.results_per_query)
        except Exception as error:  # one failed search must not lose the others
            errors.append(f"{query}: {error}")
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
        "trending_searches": trending,
    }
    out_dir = ROOT / "data" / "trends"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{report['date']}.json"
    md_path = out_dir / f"{report['date']}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(analyze.to_markdown(report), encoding="utf-8")
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

    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
