"""Runs on Kaggle, not locally: generates one video clip per job with LTX-Video.

`sensex kaggle start` fills in the settings line below and pushes this file as
a notebook. Each clip is saved to the notebook's output as `<shot id>.mp4`,
and a `sensex_done_<run>.json` file is written last so the caller can tell
the run has finished and which shots failed.
"""

import base64
import io
import json
import os
import time
import traceback

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from diffusers import LTXImageToVideoPipeline, LTXPipeline, LTXVideoTransformer3DModel
from diffusers.utils import export_to_video
from PIL import Image

SETTINGS = json.loads("__SETTINGS__")
OUT = "/kaggle/working"
MODEL = "Lightricks/LTX-Video-0.9.5"
# The distilled version needs 8 steps instead of 40 and half the memory per step,
# which is what makes a 5-second clip fit on a 15 GB T4.
DISTILLED = "https://huggingface.co/Lightricks/LTX-Video/blob/main/ltxv-2b-0.9.6-distilled-04-25.safetensors"
FPS = 24
NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted, watermark, text"

# On a T4 the attention step builds one huge table comparing every part of the video with
# every other part, which does not fit in memory for a 5-second clip. Computing it a slice
# at a time gives the same result with a fraction of the memory.
_attention = torch.nn.functional.scaled_dot_product_attention
SLICE = 1024


def _sliced_attention(query, key, value, attn_mask=None, **kwargs):
    length = query.shape[-2]
    if length <= 2 * SLICE:
        return _attention(query, key, value, attn_mask=attn_mask, **kwargs)
    parts = []
    for start in range(0, length, SLICE):
        mask = attn_mask
        if mask is not None and mask.shape[-2] == length:
            mask = mask[..., start:start + SLICE, :]
        parts.append(_attention(query[..., start:start + SLICE, :], key, value, attn_mask=mask, **kwargs))
    return torch.cat(parts, dim=-2)


torch.nn.functional.scaled_dot_product_attention = _sliced_attention

started = time.time()
print("GPU:", torch.cuda.get_device_name(0), "| jobs:", len(SETTINGS["jobs"]), flush=True)

try:
    transformer = LTXVideoTransformer3DModel.from_single_file(DISTILLED, torch_dtype=torch.bfloat16)
    image_pipe = LTXImageToVideoPipeline.from_pretrained(MODEL, transformer=transformer, torch_dtype=torch.bfloat16)
    STEPS, GUIDANCE, MAX_FRAMES = 8, 1.0, 121
    print("Using the distilled model", flush=True)
except Exception:
    traceback.print_exc()
    image_pipe = LTXImageToVideoPipeline.from_pretrained(MODEL, torch_dtype=torch.bfloat16)
    # With guidance the model runs two passes at once, so clips must be shorter to fit in memory.
    STEPS, GUIDANCE, MAX_FRAMES = 40, 3.0, 73
    print("Distilled model failed to load; using the standard model with shorter clips", flush=True)
# Turn the finished video back into pixels in small tiles and a few frames at a time;
# doing a whole clip at once needs more memory than the 15 GB GPU has.
vae = image_pipe.vae
try:
    vae.enable_tiling(tile_sample_min_height=320, tile_sample_min_width=320, tile_sample_min_num_frames=16,
                      tile_sample_stride_height=256, tile_sample_stride_width=256, tile_sample_stride_num_frames=8)
except TypeError:
    vae.enable_tiling()
vae.use_framewise_decoding = True
vae.use_framewise_encoding = True
image_pipe.enable_model_cpu_offload()   # keeps only the part in use on the GPU
text_pipe = LTXPipeline(**image_pipe.components)   # shares the same loaded parts
print(f"Model ready after {time.time() - started:.0f}s", flush=True)

results = {}
for job in SETTINGS["jobs"]:
    began = time.time()
    try:
        frames = min(int(job["seconds"] * FPS // 8) * 8 + 1, MAX_FRAMES)   # LTX needs 8n+1 frames
        common = dict(
            prompt=job["prompt"], negative_prompt=NEGATIVE,
            width=SETTINGS["width"], height=SETTINGS["height"], num_frames=frames,
            num_inference_steps=STEPS, guidance_scale=GUIDANCE,
            decode_timestep=0.05, decode_noise_scale=0.025, max_sequence_length=256,
            generator=torch.Generator(device="cuda").manual_seed(job.get("seed", 7)),
        )
        if job.get("image_b64"):
            image = Image.open(io.BytesIO(base64.b64decode(job["image_b64"]))).convert("RGB")
            image = image.resize((SETTINGS["width"], SETTINGS["height"]))
            video = image_pipe(image=image, **common).frames[0]
        else:
            video = text_pipe(**common).frames[0]
        export_to_video(video, f"{OUT}/{job['id']}.mp4", fps=FPS)
        results[job["id"]] = {"ok": True, "seconds": round(time.time() - began)}
    except Exception as error:
        traceback.print_exc()
        results[job["id"]] = {"ok": False, "error": str(error)[:400]}
    print("DONE", job["id"], results[job["id"]], f"peak GPU {torch.cuda.max_memory_allocated() / 2**30:.1f} GB", flush=True)
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.empty_cache()

with open(f"{OUT}/sensex_done_{SETTINGS['run']}.json", "w") as handle:
    json.dump({"results": results, "total_seconds": round(time.time() - started)}, handle)
print("ALL DONE", flush=True)
