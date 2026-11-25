"""Current navigation must agree; these checks do not qualify runtime evidence."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = "docs/10-spec-development/execution-state.yaml"


def _scalar(text: str, key: str, indent: str = "") -> str:
    # The execution ledger uses plain, single-line scalars for these pointers.
    # Reject absent/duplicate keys instead of accidentally reading a historical key.
    matches = re.findall(rf"^{indent}{re.escape(key)}: ([^\n]+)$", text, re.MULTILINE)
    assert len(matches) == 1, f"expected one {key} pointer, found {len(matches)}"
    return matches[0]


def test_current_and_last_checkpoint_identify_the_same_work() -> None:
    state = (ROOT / STATE).read_text(encoding="utf-8")
    assert _scalar(state, "current_checkpoint") == _scalar(state, "last_checkpoint")


def test_readme_current_checkpoint_links_to_current_evidence() -> None:
    state = (ROOT / STATE).read_text(encoding="utf-8")
    checkpoint = _scalar(state, "current_checkpoint")
    blocks = re.findall(rf"^{re.escape(checkpoint)}:\n((?:[ \t][^\n]*\n|\n)+)", state, re.MULTILINE)
    assert len(blocks) == 1, "current checkpoint must resolve to one ledger record"
    evidence = _scalar(blocks[0], "evidence", "  ")
    assert (ROOT / evidence).is_file(), "current checkpoint evidence is missing"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.findall(r"\[current [^\]]+\]\(([^)]+)\)", readme) == [evidence]


def test_active_plan_resolves_to_a_checked_in_document() -> None:
    state = (ROOT / STATE).read_text(encoding="utf-8")
    plan = _scalar(state, "active_plan")
    assert plan.startswith("docs/") and plan.endswith(".md")
    assert (ROOT / plan).is_file(), "active plan is missing"
