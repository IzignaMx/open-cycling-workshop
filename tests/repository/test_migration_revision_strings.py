"""Revision identifiers must survive YAML 1.1 numeric scalar interpretation."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_future_quote_revision_is_a_quoted_string_not_an_octal_number() -> None:
    state = (ROOT / "docs/10-spec-development/execution-state.yaml").read_text()
    match = re.search(r"^\s+quote_migration_reserved:\s*(.+)$", state, re.MULTILINE)
    assert match is not None
    scalar = match[1]
    # YAML 1.1 resolves unquoted 0010 to octal integer 8. Requiring explicit
    # quotes also preserves leading zeros under YAML 1.2 without a parser dep.
    assert re.fullmatch(r"(['\"])[0-9]{4}\1", scalar), "Migration IDs must be quoted YAML strings"
    revision = ast.literal_eval(scalar)
    assert isinstance(revision, str)
    migrations = ROOT / "services/platform/migrations/versions"
    latest = max(int(path.name[:4]) for path in migrations.glob("[0-9][0-9][0-9][0-9]_*.py"))
    assert revision == f"{latest + 1:04}"
