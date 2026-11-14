"""Fetches raw trend data: top YouTube videos per search, and Google trending searches."""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yt_dlp

# YouTube search filters: videos only, sorted by view count, uploaded within the window.
_WINDOW_FILTER = {"week": "CAMSBAgDEAE=", "month": "CAMSBAgEEAE="}
_TRENDS_NS = {"ht": "https://trends.google.com/trending/rss"}


def youtube_top_videos(query: str, window: str, limit: int) -> list[dict]:
    """The most-viewed videos uploaded in the window for one search query."""
    params = urllib.parse.urlencode({"search_query": query, "sp": _WINDOW_FILTER[window]})
    url = f"https://www.youtube.com/results?{params}"
    options = {"extract_flat": True, "quiet": True, "no_warnings": True, "playlistend": limit}
    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.extract_info(url, download=False)
    videos = []
    for entry in result.get("entries") or []:
        if not entry.get("view_count"):
            continue
        videos.append(
            {
                "id": entry["id"],
                "title": entry.get("title") or "",
                "channel": entry.get("channel") or "",
                "views": int(entry["view_count"]),
                "duration_seconds": int(entry.get("duration") or 0),
                "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry['id']}",
                "query": query,
            }
        )
    return videos


def google_trending_searches(region: str) -> list[dict]:
    """What people in the region are searching for right now."""
    url = f"https://trends.google.com/trending/rss?geo={region}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return parse_trending_rss(response.read())


def parse_trending_rss(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    searches = []
    for item in root.iter("item"):
        searches.append(
            {
                "term": item.findtext("title") or "",
                "traffic": item.findtext("ht:approx_traffic", default="", namespaces=_TRENDS_NS),
                "headlines": [
                    news.findtext("ht:news_item_title", default="", namespaces=_TRENDS_NS)
                    for news in item.findall("ht:news_item", _TRENDS_NS)
                ],
            }
        )
    return searches
