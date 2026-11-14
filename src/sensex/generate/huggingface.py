"""Free clip generation through public Hugging Face Spaces.

Two steps per shot: a still first frame from the shot prompt, then a short
silent video animated from that frame. Both run on Hugging Face's shared free
GPUs, which allow only a few minutes of use per day and can refuse or queue
requests. Set HF_TOKEN to use your own account's daily quota.
"""

import os
import shutil
from pathlib import Path

from gradio_client import Client, handle_file

IMAGE_SPACE = "mcp-tools/Qwen-Image-Fast"
VIDEO_SPACE = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
MAX_CLIP_SECONDS = 5  # longer clips cost more of the daily GPU allowance and drift off-model


class GenerationError(RuntimeError):
    pass


def _client(space: str) -> Client:
    token = os.environ.get("HF_TOKEN")
    try:
        return Client(space, token=token, verbose=False) if token else Client(space, verbose=False)
    except Exception as error:
        raise GenerationError(f"Could not reach the Space {space}: {error}") from error


def _explain(error: Exception, space: str) -> GenerationError:
    text = str(error)
    if "quota" in text.lower():
        return GenerationError(
            f"Today's free GPU allowance for {space} is used up. Try again tomorrow, or set "
            f"HF_TOKEN to use your own Hugging Face account's allowance. ({text[:200]})"
        )
    return GenerationError(f"{space} failed: {text[:300]}")


def make_frame(prompt: str, out: Path, aspect_ratio: str = "9:16", seed: int | None = None) -> Path:
    """A still image for the prompt, saved to `out`."""
    try:
        result, _ = _client(IMAGE_SPACE).predict(
            prompt=prompt, seed=seed or 0, randomize_seed=seed is None,
            aspect_ratio=aspect_ratio, api_name="/generate_image",
        )
    except GenerationError:
        raise
    except Exception as error:
        raise _explain(error, IMAGE_SPACE) from error
    path = result["path"] if isinstance(result, dict) else result
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, out)
    return out


def animate(frame: Path, prompt: str, seconds: float, out: Path) -> Path:
    """A silent video starting from `frame`, saved to `out`."""
    try:
        result = _client(VIDEO_SPACE).predict(
            input_image=handle_file(str(frame)), prompt=prompt,
            duration_seconds=min(seconds, MAX_CLIP_SECONDS), api_name="/generate_video",
        )
    except GenerationError:
        raise
    except Exception as error:
        raise _explain(error, VIDEO_SPACE) from error
    video = result[0]
    path = video["video"] if isinstance(video, dict) else video
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, out)
    return out
