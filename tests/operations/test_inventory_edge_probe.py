"""Safe evidence validator tests; actual Caddy execution is a separate gate."""

import json

import pytest

from scripts.ci.inventory_edge_probe import check_logs


def event(uri: str, *, status: int = 502) -> str:
    return json.dumps(
        {
            "level": "error",
            "logger": "http.log.error",
            "request": {"method": "GET", "uri": uri},
            "status": status,
        }
    )


def test_actual_log_evidence_requires_private_absence_and_unrelated_presence() -> None:
    private = "inventory-edge-private-canary"
    public = "inventory-edge-unrelated-canary"
    logs = (
        event("/api/v1/inventory/products/p/movements")
        + "\n"
        + event("/api/v1/inventory-other?marker=" + public)
    )
    proof = check_logs(logs, [private], public, ["/api/v1/inventory/products/p/movements"])
    assert proof == {
        "inventory_errors": 1,
        "quote_errors": 0,
        "private_request_ids_absent": True,
        "unrelated_query_preserved": True,
        "unrelated_queries_verified": 1,
        "private_queries_absent": True,
    }
    with pytest.raises(AssertionError):
        check_logs(logs + private, [private], public, ["/api/v1/inventory/products/p/movements"])
    with pytest.raises(AssertionError):
        check_logs("", [private], public, ["/api/v1/inventory/products/p/movements"])
    with pytest.raises(AssertionError):
        check_logs(
            event("/api/v1/inventory/products/p/movements", status=200) + public,
            [private],
            public,
            ["/api/v1/inventory/products/p/movements"],
        )


def test_access_only_events_cannot_masquerade_as_actual_runtime_error_evidence() -> None:
    logs = event("/api/v1/inventory") + "\n" + event("/api/v1/inventory-other?marker=unrelated")
    with pytest.raises(AssertionError):
        check_logs(
            logs.replace("http.log.error", "http.log.access"),
            ["private"],
            "unrelated",
            ["/api/v1/inventory"],
        )
    with pytest.raises(AssertionError):
        check_logs(
            logs.replace('"error"', '"info"'), ["private"], "unrelated", ["/api/v1/inventory"]
        )


def test_blocked_rerun_replaces_old_complete_artifact(tmp_path, monkeypatch) -> None:
    from scripts.ci import inventory_edge_probe as probe

    for name in (
        "infra/edge/Caddyfile",
        "infra/edge/Caddyfile.lan",
        "infra/edge/routes.caddy",
        "scripts/ci/inventory_edge_probe.py",
        "infra/docker/web.Dockerfile",
        "infra/docker/web.Dockerfile.dockerignore",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source")
    destination = tmp_path / "artifacts/inventory-read/edge-runtime-evidence.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"status":"complete"}')
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="BLOCKED"):
        probe.main()
    result = json.loads(destination.read_text())
    assert result["status"] == "incomplete"
    assert result["cases"] == []
    assert len(result["run_id"]) == 32 and result["started_at"]


def test_cleanup_failure_cannot_return_a_successful_probe(tmp_path, monkeypatch) -> None:
    from unittest.mock import MagicMock

    from scripts.ci import inventory_edge_probe as probe

    inventory, quotes = probe.private_paths(tls=False)
    paths = inventory + quotes
    logs = "\n".join(
        event(path)
        for path in [
            *paths,
            *[f"/api/v1/quotes-other?marker={probe.UNRELATED}-{i}" for i in range(4)],
        ]
    )
    responses = [(200, {}, b"")]
    for i, path in enumerate(paths):
        target = path + "?before=" + probe.PRIVATE + f"-{i}&limit=50"
        if "://" in target:
            target = target[target.index("/api/") :]
        responses.append(
            (
                200,
                {"Cache-Control": "no-store"},
                json.dumps({"target": target, "request_id": probe.REQUEST_ID}).encode(),
            )
        )
    responses += [(502, {"Cache-Control": "no-store"}, b"")] * (len(paths) + 4)
    reached = []

    def docker(*args, **kwargs):
        if args[0] == "rm":
            reached.append(True)
            raise probe.CommandFailure("exit", 1)
        if args[0] == "exec":
            return "v2.11.7 synthetic"
        if args[0] == "logs":
            return logs
        return "synthetic-container"

    monkeypatch.setattr(probe, "ThreadingHTTPServer", MagicMock())
    monkeypatch.setattr(probe.threading, "Thread", MagicMock())
    monkeypatch.setattr(probe, "docker", docker)
    monkeypatch.setattr(probe, "request", MagicMock(side_effect=responses))
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.probe("Caddyfile", tmp_path)
    assert caught.value.evidence["phase"] == "cleanup"
    assert caught.value.evidence["cleanup"]["container"] is False
    assert caught.value.evidence["cleanup"]["container_error"] == {
        "error": "command",
        "reason": "exit",
        "exit_code": 1,
    }
    assert reached == [True]


def test_missing_source_replaces_old_complete_evidence_before_hashing(
    tmp_path, monkeypatch
) -> None:
    from scripts.ci import inventory_edge_probe as probe

    path = tmp_path / "artifacts/inventory-read/edge-runtime-evidence.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"status":"complete","run_id":"old"}')
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        probe.main()
    evidence = json.loads(path.read_text())
    assert evidence["status"] == "incomplete" and evidence["cases"] == []
    assert evidence["run_id"] != "old"


def test_quote_error_receipt_requires_both_route_families_and_header_absence():
    from scripts.ci import inventory_edge_probe as probe

    inventory = ["/api/v1/inventory"]
    quotes = ["/api/v1/quotes", "/api/v1/service-orders/order-1/quotes"]
    logs = "\n".join(event(path) for path in inventory + quotes)
    logs += "\n" + event("/api/v1/inventory-other?marker=unrelated")
    proof = probe.check_logs(logs, ["private-query"], "unrelated", inventory, quote_paths=quotes)
    assert proof["inventory_errors"] == 1 and proof["quote_errors"] == 2
    assert proof["private_request_ids_absent"] is True
    with pytest.raises(AssertionError):
        probe.check_logs(
            logs + probe.REQUEST_ID, ["private-query"], "unrelated", inventory, quote_paths=quotes
        )
    with pytest.raises(AssertionError):
        probe.check_logs(
            logs.replace(event(quotes[1]), ""),
            ["private-query"],
            "unrelated",
            inventory,
            quote_paths=quotes,
        )


def test_quote_probe_plan_covers_aliases_both_route_families_and_absolute_targets():
    from scripts.ci import inventory_edge_probe as probe

    for tls in (False, True):
        inventory, quotes = probe.private_paths(tls=tls)
        assert len(inventory) == 6
        for path in (
            "/api/v1/quotes",
            "/api/v1/quotes/",
            "/api/v1/quotes/revision/authorize",
            "/api/v1/service-orders/order-1/quotes",
        ):
            assert path in quotes
        assert any("%" in path and "service" in path for path in quotes)
        assert any(path.startswith("https://" if tls else "http://") for path in quotes)


def test_each_unrelated_runtime_control_is_required():
    logs = event("/api/v1/quotes") + "\n" + event("/api/v1/quotes-other?marker=public-one")
    with pytest.raises(AssertionError):
        check_logs(
            logs, ["private"], ["public-one", "public-two"], [], quote_paths=["/api/v1/quotes"]
        )
    proof = check_logs(
        logs + "\n" + event("/api/v1/service-orders/a/b/quotes?marker=public-two"),
        ["private"],
        ["public-one", "public-two"],
        [],
        quote_paths=["/api/v1/quotes"],
    )
    assert proof["unrelated_queries_verified"] == 2
