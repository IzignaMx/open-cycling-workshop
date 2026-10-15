"""Revision identifiers must survive YAML 1.1 numeric scalar interpretation."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_implemented_quote_revision_is_a_quoted_string_not_an_octal_number() -> None:
    state = (ROOT / "docs/10-spec-development/execution-state.yaml").read_text()
    match = re.search(r"^\s+quote_migration_revision:\s*(.+)$", state, re.MULTILINE)
    assert match is not None
    scalar = match[1]
    # YAML 1.1 resolves unquoted 0010 to octal integer 8. Requiring explicit
    # quotes also preserves leading zeros under YAML 1.2 without a parser dep.
    assert re.fullmatch(r"(['\"])[0-9]{4}\1", scalar), "Migration IDs must be quoted YAML strings"
    revision = ast.literal_eval(scalar)
    assert isinstance(revision, str)
    migrations = ROOT / "services/platform/migrations/versions"
    # Task 6 consumes the old future reservation; do not silently reserve a
    # second quote migration whenever any new schema file is added.
    paths = list(migrations.glob(f"{revision}_quote_persistence.py"))
    assert len(paths) == 1
    module = ast.parse(paths[0].read_text())
    identifiers = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert identifiers == {"revision": revision, "down_revision": "0011"}
