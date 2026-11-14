"""Loads the two YAML files that describe the channel and the video tools."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


class Channel(BaseModel):
    name: str
    niche: str
    language: str
    region: str
    audience: str
    platforms: list[str]


class Scan(BaseModel):
    window: str = "week"
    results_per_query: int = 25


class ChannelConfig(BaseModel):
    channel: Channel
    queries: list[str]
    scan: Scan = Scan()


class Tool(BaseModel):
    label: str
    max_clip_seconds: float = Field(gt=0)
    credits_per_clip: float = Field(gt=0)
    daily_credits: float = Field(gt=0)
    has_audio: bool
    reference_images: bool


class ToolsConfig(BaseModel):
    max_days_per_video: int = 7
    tools: dict[str, Tool]


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_channel(path: Path | None = None) -> ChannelConfig:
    return ChannelConfig.model_validate(_read(path or CONFIG_DIR / "channel.yaml"))


def load_tools(path: Path | None = None) -> ToolsConfig:
    return ToolsConfig.model_validate(_read(path or CONFIG_DIR / "tools.yaml"))
