"""Runs open-source video models on Kaggle's free GPUs.

A script is pushed to Kaggle as a private notebook that generates one clip
per shot and saves them as its output; later the clips are downloaded into
the script folder. Kaggle gives each account a weekly allowance of free GPU
hours, far more than the Hugging Face route.
"""

import json
import os
import re
import time
from pathlib import Path

import httpx

API = "https://www.kaggle.com/api/v1"
KERNEL_TEMPLATE = Path(__file__).with_name("kaggle_kernel.py")
TIMEOUT = httpx.Timeout(60, read=300)


class KaggleError(RuntimeError):
    pass


def _headers() -> dict:
    # In a Claude cloud session the network proxy replaces this placeholder with the saved token.
    return {"Authorization": f"Bearer {os.environ.get('KAGGLE_API_TOKEN', 'proxy-injected')}"}


def _call(method: str, path: str, **kwargs):
    for attempt in range(4):
        try:
            response = httpx.request(method, API + path, headers=_headers(), timeout=TIMEOUT, **kwargs)
        except httpx.HTTPError as error:
            raise KaggleError(f"Could not reach Kaggle: {error}") from error
        if response.status_code != 429 or attempt == 3:
            break
        # Kaggle limits how often its API may be called and says how long to wait.
        time.sleep(min(int(response.headers.get("Retry-After", "60")) + 2, 200))
    if response.status_code in (401, 403):
        raise KaggleError("Kaggle refused the token. Check the saved Kaggle API token.")
    if response.status_code >= 400:
        raise KaggleError(f"Kaggle returned {response.status_code}: {response.text[:300]}")
    return response.json()


def username() -> str:
    """The account's username, read from its own notebooks or KAGGLE_USERNAME."""
    if os.environ.get("KAGGLE_USERNAME"):
        return os.environ["KAGGLE_USERNAME"]
    for kernel in _call("GET", "/kernels/list", params={"group": "profile", "pageSize": 5}):
        if kernel.get("ref"):
            return kernel["ref"].split("/")[0]
    raise KaggleError("Could not work out the Kaggle username. Set KAGGLE_USERNAME.")


def kernel_slug(folder_name: str) -> str:
    return "sensex-" + re.sub(r"[^a-z0-9]+", "-", folder_name.lower()).strip("-")[:40]


def build_source(jobs: list[dict], width: int, height: int, run: str) -> str:
    """The notebook's code with the list of clips to make filled in."""
    settings = {"jobs": jobs, "width": width, "height": height, "run": run}
    return KERNEL_TEMPLATE.read_text(encoding="utf-8").replace(
        '"__SETTINGS__"', repr(json.dumps(settings)))


def push(slug: str, source: str) -> dict:
    owner = username()
    result = _call("POST", "/kernels/push", json={
        "slug": f"{owner}/{slug}", "newTitle": slug, "text": source, "language": "python",
        "kernelType": "script", "isPrivate": True, "enableGpu": True, "enableInternet": True,
        "machineShape": "NvidiaTeslaT4",
        "datasetDataSources": [], "competitionDataSources": [], "kernelDataSources": [],
        "modelDataSources": [], "categoryIds": [],
    })
    if result.get("error"):
        raise KaggleError(f"Kaggle did not accept the notebook: {result['error']}")
    return {"owner": owner, "slug": slug, "url": result.get("url", ""), "started": time.time()}


def status(owner: str, slug: str) -> dict:
    """queued, running, complete or error. One attempt only: Kaggle rate-limits this call hard."""
    try:
        response = httpx.get(API + "/kernels/status", params={"userName": owner, "kernelSlug": slug},
                             headers=_headers(), timeout=TIMEOUT)
    except httpx.HTTPError as error:
        raise KaggleError(f"Could not reach Kaggle: {error}") from error
    if response.status_code != 200:
        raise KaggleError(f"Kaggle returned {response.status_code} for the status check")
    result = response.json()
    return {"status": str(result.get("status", "")).lower(), "failure": result.get("failureMessage") or ""}


def outputs(owner: str, slug: str) -> dict:
    """Files the notebook saved (name to download link) and its log."""
    files, token = {}, None
    log = ""
    while True:
        params = {"userName": owner, "kernelSlug": slug}
        if token:
            params["pageToken"] = token
        page = _call("GET", "/kernels/output", params=params)
        for item in page.get("files") or []:
            files[item["fileName"]] = item["url"]
        log = page.get("log") or page.get("logNullable") or log
        token = page.get("nextPageToken")
        if not token:
            return {"files": files, "log": log}


def download(url: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    headers = _headers() if "kaggle.com" in url else {}
    with httpx.stream("GET", url, headers=headers, timeout=TIMEOUT, follow_redirects=True) as response:
        if response.status_code >= 400:
            raise KaggleError(f"Download failed with {response.status_code} for {out.name}")
        with open(out, "wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return out


# ---- one script folder at a time ----

SIZES = {"9:16": (480, 832), "16:9": (832, 480), "1:1": (640, 640)}
MAX_CLIP_SECONDS = 5


def _small_jpeg(frame: Path, width: int, height: int) -> str:
    """The frame as a small base64 JPEG, so it can travel inside the notebook's code."""
    import base64
    import subprocess

    data = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(frame), "-vf",
         f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
         "-q:v", "4", "-f", "mjpeg", "-"], capture_output=True, check=True).stdout
    return base64.b64encode(data).decode()


def start(package, folder: Path, shot_ids: list[str]) -> dict:
    """Push a notebook that generates the given shots. Returns the run record, also saved to disk."""
    width, height = SIZES[package.aspect_ratio]
    shots = {shot.id: shot for shot in package.shots}
    jobs = []
    for shot_id in shot_ids:
        shot = shots[shot_id]
        job = {"id": shot_id, "prompt": shot.prompt, "seconds": min(shot.duration_seconds, MAX_CLIP_SECONDS)}
        frame = folder / "frames" / f"{shot_id}.png"
        if frame.exists():
            job["image_b64"] = _small_jpeg(frame, width, height)
        jobs.append(job)
    run = time.strftime("%Y%m%d%H%M%S")
    record = push(kernel_slug(folder.name), build_source(jobs, width, height, run))
    record.update(run=run, shots=shot_ids, with_frame=[j["id"] for j in jobs if "image_b64" in j])
    (folder / "kaggle.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def collect(folder: Path) -> dict:
    """Download finished clips for the folder's last run. `finished` is False while it still runs."""
    record_path = folder / "kaggle.json"
    if not record_path.exists():
        raise KaggleError(f"No Kaggle run has been started for {folder}.")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    result = outputs(record["owner"], record["slug"])
    done_name = f"sensex_done_{record['run']}.json"
    lines = []
    try:
        lines = [row.get("data", "").strip() for row in json.loads(result["log"] or "[]")]
    except ValueError:
        pass
    progress = [line for line in lines if line.startswith(("GPU:", "Using", "Distilled", "Model ready", "DONE", "ALL DONE"))]
    if done_name not in result["files"]:
        trouble = [line for line in lines if "Error" in line or "Traceback" in line][-3:]
        try:
            state = status(record["owner"], record["slug"])
        except KaggleError:
            state = {"status": "unknown", "failure": ""}   # the status check is often rate-limited
        if state["failure"]:
            trouble.append(state["failure"])
        return {"finished": False, "state": state["status"], "progress": progress,
                "trouble": trouble, "saved": []}
    summary = httpx.get(result["files"][done_name], timeout=TIMEOUT, follow_redirects=True).json()
    saved = []
    for shot_id, outcome in summary["results"].items():
        name = f"{shot_id}.mp4"
        if outcome.get("ok") and name in result["files"]:
            download(result["files"][name], folder / "clips" / name)
            saved.append(shot_id)
    return {"finished": True, "progress": progress, "results": summary["results"],
            "total_seconds": summary.get("total_seconds"), "saved": saved}
