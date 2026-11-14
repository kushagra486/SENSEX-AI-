import copy
import json
import subprocess
from pathlib import Path

import pytest

from sensex.config import load_tools
from sensex.script import assemble, series
from sensex.script.package import ScriptPackage, check

EXAMPLE = json.loads((Path(__file__).parents[1] / "examples" / "package.json").read_text())


def build(change=None) -> ScriptPackage:
    data = copy.deepcopy(EXAMPLE)
    if change:
        change(data)
    return ScriptPackage.model_validate(data)


def test_bible_records_episodes_and_keeps_characters():
    bible = series.record(build(), None)
    assert bible.title == "The Last Delivery"
    assert [c.id for c in bible.characters] == ["mira", "tik"]
    assert [e.number for e in bible.episodes] == [1]

    def episode_two(data):
        data["series"]["episode_number"] = 2
        data["title"] = "Ep 2"
    bible = series.record(build(episode_two), bible)
    bible = series.record(build(episode_two), bible)  # recording again replaces, not duplicates
    assert [e.number for e in bible.episodes] == [1, 2]
    assert len(bible.characters) == 2


def test_changed_character_look_is_an_error_and_skipped_episode_warns():
    bible = series.record(build(), None)

    def drift(data):
        data["characters"][0]["visual_block"] = data["characters"][0]["visual_block"].replace("yellow", "red")
        data["series"]["episode_number"] = 4
    errors, warnings = series.check_against_bible(build(drift), bible)
    assert len(errors) == 1 and "Mira" in errors[0]
    assert "episode 4" in warnings[0] and "is 2" in warnings[0]
    assert series.check_against_bible(build(), bible) == ([], [])


def test_bible_round_trips_through_its_file(tmp_path):
    bible = series.record(build(), None)
    path = series.bible_path("The Last Delivery!", tmp_path)
    assert path == tmp_path / "series" / "the-last-delivery" / "bible.json"
    path.parent.mkdir(parents=True)
    path.write_text(bible.model_dump_json())
    assert series.load_bible("The Last Delivery", tmp_path) == bible
    assert series.load_bible("Unknown", tmp_path) is None


def test_retention_warnings():
    def weak(data):
        data["shots"][0]["on_screen_text"] = ""
        for shot in data["shots"]:
            shot["dialogue"] = shot["voiceover"] = ""
    warnings = " ".join(check(build(weak), load_tools()).warnings)
    assert "opening has no on-screen text" in warnings
    assert "no dialogue or voiceover" in warnings
    assert check(build(), load_tools()).warnings == []


def make_clip(path, seconds, size="640x360", audio=True):
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
               f"testsrc=size={size}:rate=24:duration={seconds}"]
    if audio:
        command += ["-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}", "-c:a", "aac"]
    subprocess.run(command + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_assemble_joins_clips_to_script_length(tmp_path):
    package = build()
    (tmp_path / "clips").mkdir()
    (tmp_path / "audio").mkdir()
    assert assemble.missing_clips(package, tmp_path) == [s.id for s in package.shots]
    with pytest.raises(FileNotFoundError, match="S1"):
        assemble.assemble(package, tmp_path)

    for index, shot in enumerate(package.shots):
        # one clip is too short, one is silent, sizes differ: all must still fit the script
        seconds = 2 if index == 1 else shot.duration_seconds + 1
        make_clip(tmp_path / "clips" / f"{shot.id}.mp4", seconds,
                  size="360x640" if index % 2 else "640x360", audio=index != 2)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=600:duration=3",
                    str(tmp_path / "audio" / "S6.mp3")], check=True)

    final = assemble.assemble(package, tmp_path)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "json", str(final)], capture_output=True, text=True, check=True).stdout
    info = json.loads(probe)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert float(info["format"]["duration"]) == pytest.approx(package.runtime_seconds, abs=0.7)


def test_site_embeds_every_script_series_and_trend_report():
    from sensex import site
    data = site.collect()
    assert {s["folder"] for s in data["scripts"]} >= {"2026-11-14-pintu-pigeon-ep1"}
    assert data["series"] and data["trends"]["notes"].strip()
    html = site.build().read_text()
    assert "/*DATA*/" not in html and "Pintu Pigeon" in html
    payload = html.split('id="data">')[1].split("</script>")[0]
    assert json.loads(payload)["scripts"]
