import pytest

from sensex.generate import huggingface as hf


class FakeClient:
    calls = []
    error = None

    def __init__(self, space, **kwargs):
        self.space = space

    def predict(self, **kwargs):
        FakeClient.calls.append((self.space, kwargs))
        if FakeClient.error:
            raise FakeClient.error
        return FakeClient.result


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    FakeClient.calls, FakeClient.error = [], None
    monkeypatch.setattr(hf, "Client", FakeClient)
    monkeypatch.setattr(hf, "handle_file", lambda path: {"path": path})


def test_frame_then_clip_are_saved_where_asked(tmp_path):
    source = tmp_path / "made.bin"
    source.write_bytes(b"data")
    FakeClient.result = ({"path": str(source)}, 7)
    frame = hf.make_frame("a pigeon", tmp_path / "frames" / "S1.png", "9:16")
    FakeClient.result = ({"video": str(source)}, 7)
    clip = hf.animate(frame, "a pigeon flies", 8, tmp_path / "clips" / "S1.mp4")
    assert frame.read_bytes() == clip.read_bytes() == b"data"
    image_call, video_call = FakeClient.calls
    assert image_call[0] == hf.IMAGE_SPACE and image_call[1]["aspect_ratio"] == "9:16"
    assert video_call[0] == hf.VIDEO_SPACE
    assert video_call[1]["duration_seconds"] == hf.MAX_CLIP_SECONDS  # 8s asked, capped


def test_quota_refusal_is_explained(tmp_path):
    FakeClient.error = RuntimeError("You have exceeded your ZeroGPU runs limit. more quota")
    with pytest.raises(hf.GenerationError, match="allowance"):
        hf.make_frame("x", tmp_path / "f.png")


def test_shot_generation_reuses_character_reference_and_voice(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from sensex.generate import shots
    from sensex.script.package import ScriptPackage

    package = ScriptPackage.model_validate(
        json.loads((Path(__file__).parents[1] / "examples" / "package.json").read_text()))
    made = []

    def fake(kind):
        def run(*args, **kwargs):
            out = next(a for a in args if isinstance(a, Path) and a.suffix in (".png", ".mp4", ".wav")
                       and not a.exists())
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(kind.encode())
            made.append((kind, out.relative_to(tmp_path).as_posix(), args, kwargs))
            return out
        return run

    for name in ("make_frame", "edit_frame", "animate", "speak"):
        monkeypatch.setattr(hf, name, fake(name))
    monkeypatch.setattr(shots, "_seconds", lambda path: 3.0)
    folder = tmp_path / "scripts" / "ep1"
    by_id = {shot.id: shot for shot in package.shots}

    shots.generate_shot(package, by_id["S1"], folder, root=tmp_path)   # no character, no line
    shots.generate_shot(package, by_id["S2"], folder, root=tmp_path)   # Mira and Tik, Mira speaks
    notes = shots.generate_shot(package, by_id["S6"], folder, root=tmp_path)  # Mira, voiceover
    kinds = [(kind, path) for kind, path, _, _ in made]
    assert kinds == [
        ("make_frame", "scripts/ep1/frames/S1.png"), ("animate", "scripts/ep1/clips/S1.mp4"),
        ("make_frame", "series/the-last-delivery/refs/mira.png"),
        ("edit_frame", "scripts/ep1/frames/S2.png"), ("animate", "scripts/ep1/clips/S2.mp4"),
        ("speak", "scripts/ep1/audio/S2.wav"),
        ("edit_frame", "scripts/ep1/frames/S6.png"), ("animate", "scripts/ep1/clips/S6.mp4"),
        ("speak", "scripts/ep1/audio/S6.wav"),
    ]
    sample = tmp_path / "series" / "the-last-delivery" / "voices" / "mira.wav"
    assert sample.exists()
    first_voice, second_voice = made[5], made[8]
    assert first_voice[2][2] is None and second_voice[2][2] == sample   # later lines clone the first
    assert first_voice[2][0] == "Nobody has lived here for ten years, Tik."
    assert any("already exists" in note for note in
               shots.generate_shot(package, by_id["S6"], folder, voice=False, root=tmp_path))
    assert notes and shots.spoken_line(by_id["S1"]) is None
