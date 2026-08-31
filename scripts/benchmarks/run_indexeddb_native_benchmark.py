#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = ROOT / "scripts/benchmarks"
BROWSER_DRIVER = BENCHMARK_DIR / "run_indexeddb_benchmark_browser.mjs"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def server():
    def handler(*args: Any, **kwargs: Any) -> QuietHandler:
        return QuietHandler(*args, directory=str(BENCHMARK_DIR), **kwargs)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_port
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def detect_url_block_policy(policy_dir: Path) -> str | None:
    if not policy_dir.is_dir():
        return None
    for path in sorted(policy_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        blocklist = payload.get("URLBlocklist")
        if isinstance(blocklist, list) and "*" in blocklist:
            return str(path)
    return None


def main() -> int:
    policy_dir = Path(os.getenv("OCWP_CHROMIUM_POLICY_DIR", "/etc/chromium/policies/managed"))
    blocking_policy = detect_url_block_policy(policy_dir)
    if blocking_policy is not None:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "chromium managed URLBlocklist blocks all navigations",
                    "policy": blocking_policy,
                }
            )
        )
        return 2

    node = "node" if sys.platform != "win32" else os.getenv("OCWP_NODE_BIN", "node")
    timeout_seconds = int(os.getenv("OCWP_INDEXEDDB_BENCHMARK_TIMEOUT", "300"))

    with server() as port:
        total = os.getenv("OCWP_INDEXEDDB_BENCHMARK_TOTAL", "100000")
        url = f"http://127.0.0.1:{port}/indexeddb_native_100k.html?total={total}"
        env = dict(os.environ)
        env["OCWP_BENCHMARK_TIMEOUT_MS"] = str(timeout_seconds * 1000)
        try:
            result = subprocess.run(
                [node, str(BROWSER_DRIVER), url],
                text=True,
                capture_output=True,
                timeout=timeout_seconds + 60,
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "benchmark browser run timed out in this environment",
                    }
                )
            )
            return 2
        except OSError as error:
            print(json.dumps({"status": "blocked", "reason": f"node unavailable: {error}"}))
            return 2

    output = result.stdout.strip()
    try:
        payload = json.loads(html.unescape(output))
    except json.JSONDecodeError:
        print(json.dumps({"status": "blocked", "reason": "browser driver produced no result",
                          "driver_stdout": output[-500:], "driver_stderr": result.stderr[-500:]}))
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
