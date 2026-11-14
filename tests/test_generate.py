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
