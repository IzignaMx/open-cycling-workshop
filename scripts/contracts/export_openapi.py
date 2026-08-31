#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "services" / "platform" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cycling_workshop.app import create_app  # noqa: E402
from cycling_workshop.settings import Settings  # noqa: E402

OUTPUT = ROOT / "packages" / "api-client" / "openapi.json"


def render() -> str:
    app = create_app(
        settings=Settings(
            environment="contract",
            database_url="sqlite+pysqlite:///:memory:",
            log_level="WARNING",
            auth_secret="contract-secret-long-enough-for-deterministic-export",
        )
    )
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"OpenAPI drift detected: regenerate {OUTPUT.relative_to(ROOT)}")
            return 1
        print("OpenAPI contract: OK")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
