import subprocess

import pytest
from pydantic import ValidationError

from sensex.clips import analyze, cut


def segment(start, end, text):
    words = text.split()
    step = (end - start) / len(words)
    return {"start": start, "end": end, "text": text,
            "words": [{"start": round(start + i * step, 2), "end": round(start + (i + 1) * step, 2),
                       "word": w} for i, w in enumerate(words)]}


SEGMENTS = [segment(i * 10.0, i * 10.0 + 9.0, f"sentence number {i} goes here") for i in range(12)]


def test_candidates_follow_sentences_and_prefer_the_loud_busy_part():
    loudness = [0.05] * 120
    loudness[60:90] = [0.6] * 30
    cuts = [62.0, 66.0, 70.0, 75.0, 81.0]
    found = analyze.find_candidates(loudness, cuts, SEGMENTS, 120.0, min_len=20, max_len=40)
    best = found[0]
    assert 50 <= best["start"] and best["end"] <= 100
    starts = {s["start"] for s in SEGMENTS}
    ends = {s["end"] for s in SEGMENTS}
    for row in found:
        assert row["start"] in starts and row["end"] in ends
        assert 20 <= row["end"] - row["start"] <= 40
    for a in found:
        for b in found:
            assert a is b or a["end"] <= b["start"] or a["start"] >= b["end"]
    assert "sentence number" in best["text"]


def test_candidates_without_speech_use_a_time_grid():
    loudness = [0.1] * 90
    loudness[40:60] = [0.8] * 20
    found = analyze.find_candidates(loudness, [], [], 90.0)
    assert found and found[0]["start"] <= 45 <= found[0]["end"]
    assert found[0]["text"] == ""


def test_no_candidates_for_a_video_shorter_than_one_clip():
    assert analyze.find_candidates([0.1] * 5, [], [], 5.0) == []


def test_caption_chunks_are_relative_to_the_clip():
    chunks = cut.caption_chunks(SEGMENTS, 10.0, 19.0)
    assert [c["text"] for c in chunks] == ["sentence number 1 goes", "here"]
    assert chunks[0]["start"] == 0.0 and chunks[-1]["end"] == 9.0
    srt = cut.to_srt(chunks)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:07,200\nsentence number 1 goes\n")


def plan(**change):
    clip = {"id": "c1", "start": 0, "end": 30, "title": "T", "caption": "C",
            "why": "A complete joke with setup and payoff."} | change
    return {"rights": "My own gameplay recording.", "clips": [clip]}


def test_plan_rejects_bad_times_missing_rights_and_overlong_clips():
    cut.ClipPlan.model_validate(plan())
    for bad in (plan(end=0), plan(end=500), plan(id="bad id"), {**plan(), "rights": ""}):
        with pytest.raises(ValidationError):
            cut.ClipPlan.model_validate(bad)


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24:duration=12",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
         "-af", "volume='if(between(t,6,9),1.0,0.05)':eval=frame",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
        check=True,
    )
    return path


def test_loudness_and_duration_are_measured_from_a_real_file(sample_video):
    assert analyze.duration_seconds(sample_video) == pytest.approx(12, abs=0.2)
    levels = analyze.loudness_per_second(sample_video)
    assert len(levels) in (12, 13)
    assert levels[7] > 5 * levels[2]
    assert isinstance(analyze.scene_cut_times(sample_video), list)


@pytest.mark.parametrize("layout", ["blur", "crop"])
def test_cut_makes_a_vertical_clip_with_captions(sample_video, tmp_path, layout):
    clip = cut.Clip(id=f"c-{layout}", start=2, end=6, title="T", caption="C",
                    why="Test clip for the cutter.", layout=layout)
    transcript = [segment(2.5, 5.5, "hello this is a caption test")]
    out = cut.cut_clip(sample_video, clip, transcript, tmp_path)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True).stdout.split()
    assert probe[0] == "1080,1920"
    assert float(probe[1]) == pytest.approx(4, abs=0.2)
    assert (tmp_path / f"c-{layout}.srt").exists()
    sheet = cut.review_sheet(cut.ClipPlan(rights="My own recording.", clips=[clip]), {clip.id: out})
    assert "Nothing here has been posted" in sheet and out.name in sheet
