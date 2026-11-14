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


def build_source(jobs: list[dict], width: int, height: int) -> str:
    """The notebook's code with the list of clips to make filled in."""
    settings = {"jobs": jobs, "width": width, "height": height}
    return KERNEL_TEMPLATE.read_text(encoding="utf-8").replace(
        '"__SETTINGS__"', repr(json.dumps(settings)))


def push(slug: str, source: str) -> dict:
    owner = username()
    result = _call("POST", "/kernels/push", json={
        "slug": f"{owner}/{slug}", "newTitle": slug, "text": source, "language": "python",
        "kernelType": "script", "isPrivate": True, "enableGpu": True, "enableInternet": True,
        "datasetDataSources": [], "competitionDataSources": [], "kernelDataSources": [],
        "modelDataSources": [], "categoryIds": [],
    })
    if result.get("error"):
        raise KaggleError(f"Kaggle did not accept the notebook: {result['error']}")
    return {"owner": owner, "slug": slug, "url": result.get("url", ""), "started": time.time()}


def status(owner: str, slug: str) -> dict:
    result = _call("GET", "/kernels/status", params={"userName": owner, "kernelSlug": slug})
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
