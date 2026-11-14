"""Builds the one-page web view of everything in the repo: scripts, series, trends."""

import json
from datetime import datetime
from pathlib import Path

from sensex.config import ROOT, load_channel, load_tools
from sensex.script.package import ScriptPackage, budget, check

TEMPLATE = Path(__file__).with_name("site_template.html")
NOTES_HEADING = "## What this means for us"


def collect(root: Path = ROOT) -> dict:
    tools = load_tools()
    scripts = []
    for path in sorted(root.glob("scripts/*/package.json"), reverse=True):
        package = ScriptPackage.model_validate_json(path.read_text(encoding="utf-8"))
        spend = budget(package, tools)
        scripts.append({
            "folder": path.parent.name,
            "package": package.model_dump(),
            "runtime": package.runtime_seconds,
            "days": spend.days_needed,
            "budget": spend.model_dump(),
            "warnings": check(package, tools).warnings,
        })
    series = [json.loads(path.read_text(encoding="utf-8"))
              for path in sorted(root.glob("series/*/bible.json"))]
    trends = None
    reports = sorted(root.glob("data/trends/*.json"))
    if reports:
        trends = json.loads(reports[-1].read_text(encoding="utf-8"))
        written = reports[-1].with_suffix(".md")
        text = written.read_text(encoding="utf-8") if written.exists() else ""
        trends["notes"] = text[text.index(NOTES_HEADING) + len(NOTES_HEADING):] if NOTES_HEADING in text else ""
    return {
        "built": datetime.now().strftime("%d %b %Y, %H:%M"),
        "tools": {name: tool.model_dump() for name, tool in tools.tools.items()},
        "max_days": tools.max_days_per_video,
        "channel": load_channel().channel.model_dump(),
        "scripts": scripts,
        "series": series,
        "trends": trends,
    }


def build(root: Path = ROOT) -> Path:
    data = json.dumps(collect(root), ensure_ascii=False).replace("</", "<\\/")
    out = root / "site" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", data), encoding="utf-8")
    return out
