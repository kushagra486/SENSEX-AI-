from sensex.trends.analyze import analyze, length_bucket, to_markdown
from sensex.trends.sources import parse_trending_rss


def video(id, title, views, seconds, query="ai story", channel="Chan"):
    return {"id": id, "title": title, "channel": channel, "views": views,
            "duration_seconds": seconds, "url": f"https://youtu.be/{id}", "query": query}


VIDEOS = [
    video("a", "She Was the SECRET Daughter of a Dragon King?", 900_000, 45),
    video("b", "Secret billionaire revenge story Part 2", 300_000, 50, channel="Other"),
    video("c", "Dragon gameplay but AI made it", 100_000, 700, query="ai gameplay"),
    video("a", "She Was the SECRET Daughter of a Dragon King?", 900_000, 45, query="ai gameplay"),
]


def test_length_buckets():
    assert length_bucket(60) == "short (up to 1 min)"
    assert length_bucket(61) == "short (1-3 min)"
    assert length_bucket(2000) == "very long (30 min+)"


def test_analyze_dedupes_ranks_and_finds_patterns():
    result = analyze(VIDEOS)
    assert result["video_count"] == 3
    assert [v["id"] for v in result["top_videos"]] == ["a", "b", "c"]
    assert result["median_views"] == 300_000
    words = {row["word"]: row["videos"] for row in result["title_words"]}
    assert words["secret"] == 2 and words["dragon"] == 2
    patterns = {row["pattern"]: row["videos"] for row in result["title_patterns"]}
    assert patterns["secret / hidden identity"] == 2
    assert patterns["asks a question"] == 1
    assert patterns["episode or part"] == 1
    assert result["lengths"][0]["length"] == "short (up to 1 min)"
    assert result["repeat_channels"] == [{"channel": "Chan", "videos": 2}]


def test_analyze_handles_no_videos():
    assert analyze([]) == {"video_count": 0}


def test_parse_trending_rss():
    xml = b"""<rss xmlns:ht="https://trends.google.com/trending/rss"><channel>
    <item><title>ind vs aus</title><ht:approx_traffic>500000+</ht:approx_traffic>
    <ht:news_item><ht:news_item_title>India win</ht:news_item_title></ht:news_item></item>
    </channel></rss>"""
    assert parse_trending_rss(xml) == [
        {"term": "ind vs aus", "traffic": "500000+", "headlines": ["India win"]}
    ]


def test_markdown_report_lists_videos_and_failures():
    report = {"date": "2026-11-14", "niche": "AI stories", "region": "IN", "window": "week",
              "errors": ["ai horror: timeout"], "analysis": analyze(VIDEOS),
              "trending_searches": [{"term": "ind vs aus", "traffic": "500000+", "headlines": []}]}
    text = to_markdown(report)
    assert "ai horror: timeout" in text
    assert "She Was the SECRET Daughter of a Dragon King?" in text
    assert "**ind vs aus** (500000+)" in text


def test_rising_words_compares_with_previous_report():
    from sensex.trends.analyze import rising_words
    previous = {"title_words": [{"word": "horror", "videos": 5}, {"word": "dragon", "videos": 9}]}
    current = {"title_words": [{"word": "horror", "videos": 12}, {"word": "dragon", "videos": 9},
                               {"word": "diwali", "videos": 4}]}
    assert rising_words(current, previous) == [
        {"word": "horror", "now": 12, "before": 5},
        {"word": "diwali", "now": 4, "before": 0},
    ]


def test_markdown_has_separate_short_video_section_and_rising_words():
    report = {"date": "2026-11-15", "niche": "AI stories", "region": "IN", "window": "week",
              "errors": [], "analysis": analyze(VIDEOS), "shorts_analysis": analyze(VIDEOS[:2]),
              "compared_with": "2026-11-14",
              "rising_words": [{"word": "horror", "now": 12, "before": 5}], "trending_searches": []}
    text = to_markdown(report)
    assert "## Long-form: top videos" in text and "## Short videos: top videos" in text
    assert "## Rising since 2026-11-14" in text and "horror (5 to 12 videos)" in text
