"""Turns raw video lists into the patterns a script writer needs."""

import re
from collections import Counter
from statistics import median

_STOPWORDS = set(
    "a an and are as at be but by for from has have he her his how i in into is it its me my "
    "of on or she so that the their them they this to was we were what when who why will with "
    "you your video videos full new official ft vs part ep episode hd 4k".split()
)

# Title habits worth knowing about; each is counted across the top videos.
_TITLE_PATTERNS = {
    "has a number": r"\d",
    "asks a question": r"\?",
    "ALL-CAPS word": r"\b[A-Z]{4,}\b",
    "ellipsis cliffhanger": r"\.\.\.|…",
    "POV": r"\bpov\b",
    "episode or part": r"\b(part|episode|ep)\s*\.?\s*\d+",
    "hashtag in title": r"#\w+",
    "secret / hidden identity": r"\b(secret|hidden|unaware|didn'?t know|disguise)",
    "revenge / betrayal": r"\b(revenge|betray|rejected|divorce|abandon)",
}


def length_bucket(seconds: int) -> str:
    if seconds <= 60:
        return "short (up to 1 min)"
    if seconds <= 180:
        return "short (1-3 min)"
    if seconds <= 600:
        return "mid (3-10 min)"
    if seconds <= 1800:
        return "long (10-30 min)"
    return "very long (30 min+)"


def _dedupe(videos: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for video in videos:
        seen.setdefault(video["id"], video)
    return list(seen.values())


def _title_words(title: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z']{2,}", title.lower())
    return {word for word in words if word not in _STOPWORDS}


def analyze(videos: list[dict], top_n: int = 25) -> dict:
    """Summarise what the most-viewed recent videos have in common."""
    unique = _dedupe(videos)
    if not unique:
        return {"video_count": 0}
    ranked = sorted(unique, key=lambda video: video["views"], reverse=True)

    by_query: dict[str, list[dict]] = {}
    for video in videos:
        by_query.setdefault(video["query"], []).append(video)
    queries = [
        {
            "query": query,
            "videos": len(group),
            "median_views": int(median(v["views"] for v in group)),
            "top_views": max(v["views"] for v in group),
            "top_title": max(group, key=lambda v: v["views"])["title"],
        }
        for query, group in by_query.items()
    ]
    queries.sort(key=lambda row: row["median_views"], reverse=True)

    lengths: dict[str, list[int]] = {}
    for video in unique:
        lengths.setdefault(length_bucket(video["duration_seconds"]), []).append(video["views"])
    length_rows = [
        {"length": bucket, "videos": len(views), "median_views": int(median(views))}
        for bucket, views in lengths.items()
    ]
    length_rows.sort(key=lambda row: row["median_views"], reverse=True)

    word_counts: Counter[str] = Counter()
    word_views: Counter[str] = Counter()
    for video in unique:
        for word in _title_words(video["title"]):
            word_counts[word] += 1
            word_views[word] += video["views"]
    words = [
        {"word": word, "videos": count, "total_views": word_views[word]}
        for word, count in word_counts.most_common(40)
        if count >= 2
    ]

    patterns = []
    for name, regex in _TITLE_PATTERNS.items():
        flags = 0 if name == "ALL-CAPS word" else re.IGNORECASE
        matched = [v for v in unique if re.search(regex, v["title"], flags)]
        if matched:
            patterns.append(
                {
                    "pattern": name,
                    "videos": len(matched),
                    "share": round(len(matched) / len(unique), 2),
                    "median_views": int(median(v["views"] for v in matched)),
                }
            )
    patterns.sort(key=lambda row: row["videos"], reverse=True)

    channels = Counter(video["channel"] for video in unique if video["channel"])
    return {
        "video_count": len(unique),
        "median_views": int(median(v["views"] for v in unique)),
        "top_videos": ranked[:top_n],
        "queries": queries,
        "lengths": length_rows,
        "title_words": words,
        "title_patterns": patterns,
        "repeat_channels": [
            {"channel": name, "videos": count} for name, count in channels.most_common(10) if count >= 2
        ],
    }


def _table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |")
    return "\n".join(lines)


def to_markdown(report: dict) -> str:
    """A readable version of the trend report."""
    analysis = report["analysis"]
    parts = [
        f"# Trend report: {report['date']}",
        f"Niche: {report['niche']}. Window: videos uploaded in the last {report['window']}. "
        f"{analysis.get('video_count', 0)} videos scanned.",
    ]
    if report.get("errors"):
        parts.append("**Searches that failed:** " + "; ".join(report["errors"]))
    if not analysis.get("video_count"):
        parts.append("No videos were found.")
        return "\n\n".join(parts) + "\n"

    parts.append("## Which searches are hottest\n\n" + _table(
        ["Search", "Videos", "Median views", "Top views", "Top title"],
        [[q["query"], q["videos"], f"{q['median_views']:,}", f"{q['top_views']:,}", q["top_title"]]
         for q in analysis["queries"]],
    ))
    parts.append("## Which lengths get the views\n\n" + _table(
        ["Length", "Videos", "Median views"],
        [[row["length"], row["videos"], f"{row['median_views']:,}"] for row in analysis["lengths"]],
    ))
    parts.append("## Title habits\n\n" + _table(
        ["Habit", "Videos", "Share", "Median views"],
        [[p["pattern"], p["videos"], f"{p['share']:.0%}", f"{p['median_views']:,}"]
         for p in analysis["title_patterns"]],
    ))
    parts.append("## Words that keep appearing in titles\n\n" + ", ".join(
        f"{w['word']} ({w['videos']})" for w in analysis["title_words"]
    ))
    parts.append("## Top videos\n\n" + _table(
        ["Views", "Length", "Title", "Channel", "Link"],
        [[f"{v['views']:,}", f"{v['duration_seconds'] // 60}:{v['duration_seconds'] % 60:02d}",
          v["title"], v["channel"], v["url"]] for v in analysis["top_videos"]],
    ))
    if analysis["repeat_channels"]:
        parts.append("## Channels with several hits\n\n" + ", ".join(
            f"{c['channel']} ({c['videos']})" for c in analysis["repeat_channels"]
        ))
    if report.get("trending_searches"):
        parts.append(f"## Trending Google searches ({report['region']})\n\n" + "\n".join(
            f"- **{s['term']}** ({s['traffic']})" + (f": {s['headlines'][0]}" if s["headlines"] else "")
            for s in report["trending_searches"]
        ))
    return "\n\n".join(parts) + "\n"
