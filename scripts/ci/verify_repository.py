#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    "LICENSE",
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "ARCHITECTURE.md",
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "tsconfig.base.json",
    ".python-version",
    ".nvmrc",
)

REQUIRED_DIRS = (
    "apps/web",
    "services/platform",
    "packages/ui",
    "packages/api-client",
    "packages/plugin-sdk",
    "packages/branding",
    "infra/compose",
    "fixtures/minimal",
    "fixtures/demo-workshop",
    "fixtures/load",
)


def main() -> int:
    missing_files = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    missing_dirs = [path for path in REQUIRED_DIRS if not (ROOT / path).is_dir()]

    if missing_files or missing_dirs:
        if missing_files:
            print("Missing files:")
            for path in missing_files:
                print(f"  - {path}")
        if missing_dirs:
            print("Missing directories:")
            for path in missing_dirs:
                print(f"  - {path}")
        return 1

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text:
        print("LICENSE does not contain GNU AGPL text")
        return 1

    print("Repository contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
