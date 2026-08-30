#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = ROOT / "scripts/benchmarks"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@contextmanager
def server():
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(BENCHMARK_DIR), **kwargs)
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
    chromium = shutil.which("chromium")
    if chromium is None:
        print(json.dumps({"status": "blocked", "reason": "chromium unavailable"}))
        return 2
    policy_dir = Path(os.getenv("OCWP_CHROMIUM_POLICY_DIR", "/etc/chromium/policies/managed"))
    blocking_policy = detect_url_block_policy(policy_dir)
    if blocking_policy is not None:
        print(json.dumps({
            "status": "blocked",
            "reason": "chromium managed URLBlocklist blocks all navigations",
            "policy": blocking_policy,
        }))
        return 2
    try:
        preflight = subprocess.run(
            [chromium, "--headless=new", "--no-sandbox", "--disable-gpu", "--dump-dom", "data:text/html,<html><body>ocwp</body></html>"],
            text=True,
            capture_output=True,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"status": "blocked", "reason": "chromium headless preflight timed out in this environment"}))
        return 2
    if preflight.returncode != 0 or "ocwp" not in preflight.stdout:
        print(json.dumps({"status": "blocked", "reason": "chromium headless preflight could not render a trivial page"}))
        return 2
    with server() as port, tempfile.TemporaryDirectory(prefix="ocwp-chromium-") as profile:
        total = os.getenv("OCWP_INDEXEDDB_BENCHMARK_TOTAL", "100000")
        result = subprocess.run(
            [
                chromium,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=60000",
                "--dump-dom",
                f"http://127.0.0.1:{port}/indexeddb_native_100k.html?total={total}",
            ],
            text=True,
            capture_output=True,
            timeout=90,
        )
        match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.DOTALL)
        if match is None:
            print(result.stdout[-4000:])
            print(result.stderr[-4000:])
            return 1
        payload = json.loads(html.unescape(match.group(1)))
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
