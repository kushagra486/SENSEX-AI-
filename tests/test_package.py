import copy
import json
from pathlib import Path

import pytest

from sensex.config import load_tools
from sensex.script.package import ScriptPackage, budget, check
from sensex.script.render import render

EXAMPLE = json.loads((Path(__file__).parents[1] / "examples" / "package.json").read_text())
TOOLS = load_tools()


def build(change=None) -> ScriptPackage:
    data = copy.deepcopy(EXAMPLE)
    if change:
        change(data)
    return ScriptPackage.model_validate(data)


def errors(change) -> str:
    return " ".join(check(build(change), TOOLS).errors)


def test_example_package_passes():
    result = check(build(), TOOLS)
    assert result.errors == []


def test_shot_longer_than_tool_limit_is_rejected():
    def too_long(data):
        data["shots"][1]["duration_seconds"] = 9
    assert "clip limit" in errors(too_long)


def test_prompt_missing_character_description_is_rejected():
    def drop_description(data):
        data["shots"][3]["prompt"] = "Vertical 9:16. Mira looks up at the dark window."
    assert "visual_block" in errors(drop_description)


def test_unknown_tool_and_character_are_rejected():
    def unknown(data):
        data["shots"][0]["tool"] = "sora"
        data["shots"][1]["characters"].append("ghost")
    message = errors(unknown)
    assert "unknown tool 'sora'" in message and "unknown character 'ghost'" in message


def test_runtime_far_from_target_is_rejected():
    def wrong_target(data):
        data["target_runtime_seconds"] = 90
    assert "target runtime" in errors(wrong_target)


def test_series_episode_needs_series_section():
    def no_series(data):
        data["series"] = None
    assert "series" in errors(no_series)


def test_too_many_days_of_credits_is_rejected():
    def all_veo(data):
        data["shots"] = [dict(data["shots"][2], id=f"S{i}") for i in range(24)]
        data["target_runtime_seconds"] = 192
    assert "days of free credits" in errors(all_veo)


def test_dialogue_on_silent_tool_warns():
    def silent(data):
        data["shots"][3]["dialogue"] = "Mira: Hello?"
    result = check(build(silent), TOOLS)
    assert result.ok and any("silent" in warning for warning in result.warnings)


def test_budget_counts_clips_credits_and_days():
    spend = budget(build(), TOOLS)
    assert spend.clips == {"dreamina": 4, "veo": 2}
    assert spend.credits == {"dreamina": 80, "veo": 2}
    assert spend.days == {"dreamina": 1, "veo": 1}
    assert spend.days_needed == 1


def test_render_contains_prompts_timeline_and_posting():
    package = build()
    text = render(package, TOOLS)
    for shot in package.shots:
        assert shot.prompt in text
    assert "### S2 · 0:04-0:12 · 8s · Veo (Gemini Pro)" in text
    assert "## Edit timeline" in text and package.posting.title in text
    assert package.series.cliffhanger in text


def test_missing_required_field_fails_validation():
    with pytest.raises(Exception):
        build(lambda data: data.pop("original_twist"))
