"""Pure closed claims for the planned one-shot H/S consumer; never runtime proof.

No process, socket, SQL, file writer or executable measurement entrypoint lives here.
Expected identity comes from the separately reviewed same-job Actions guard.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from typing import Any, NoReturn, cast

PUBLIC_PROPOSAL_SHA256 = "1951f853a6e6cb1f57d0f66501726cfa370c33e9dd167b9f9a118aae463b8971"
SECOND = 1_000_000_000
CODES = frozenset(
    {
        "preflight",
        "role_unverified",
        "protocol",
        "setup_deadline",
        "experiment_deadline",
        "case_deadline",
        "identity",
        "observer_unknown",
        "reap_unknown",
        "pressure",
        "interrupted",
        "cleanup_unknown",
    }
)
IDENTITY_KEYS = frozenset(
    {
        "commit",
        "tree",
        "worker_image",
        "pg_image",
        "authorization",
        "nonce",
        "run_id",
        "workflow_id",
        "run_number",
        "run_attempt",
        "repository",
        "repository_id",
        "workflow_path",
        "ref",
        "database",
        "role",
    }
)
TIMES = ("start_ns", "ready_ns", "stop_ns", "reaped_ns", "absent_ns")
FLAGS = ("read_only", "clean_session", "same_backend")


class OwnershipEvidenceError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid_ownership_evidence")


def _require(condition: bool) -> None:
    if not condition:
        raise OwnershipEvidenceError() from None


def _keys(value: Any, keys: Collection[str]) -> None:
    _require(type(value) is dict and set(value) == set(keys))


def _integer(value: Any, low: int = 0, high: int = 2**63 - 1) -> None:
    _require(type(value) is int and low <= value <= high)


def _matches(value: Any, pattern: str) -> None:
    _require(type(value) is str and re.fullmatch(pattern, value) is not None)


def _identity(value: Any, expected: dict[str, object]) -> None:
    _keys(value, IDENTITY_KEYS)
    _keys(expected, IDENTITY_KEYS)
    for name in ("commit", "tree"):
        _matches(value[name], r"[0-9a-f]{40}")
    for name in ("worker_image", "pg_image"):
        _matches(value[name], r"sha256:[0-9a-f]{64}")
    _matches(value["nonce"], r"[0-9a-f]{32}")
    for name in ("run_id", "workflow_id"):
        _matches(value[name], r"[1-9][0-9]{0,19}")
    for name in ("database", "role"):
        _matches(value[name], r"[a-z][a-z0-9_]{0,62}")
    for name in ("run_number", "run_attempt"):
        _integer(value[name], 1, 1)
    _integer(value["repository_id"], 1327018760, 1327018760)
    fixed = {
        "repository": "IzignaMx/open-cycling-workshop",
        "workflow_path": ".github/workflows/quote-ownership-measurement.yml",
        "ref": "refs/heads/main",
        "authorization": PUBLIC_PROPOSAL_SHA256,
    }
    _require(all(value[k] == v for k, v in fixed.items()))
    _require(value == expected)
    # Equality alone would permit True == 1 in a supposedly trusted expected map.
    _require(all(type(value[k]) is type(expected[k]) for k in IDENTITY_KEYS))


def _backend(value: Any, identity: dict[str, object]) -> None:
    _keys(value, {"pid", "start_us", "database", "role"})
    _integer(value["pid"], 1, 2**31 - 1)
    _integer(value["start_us"], 1)
    _require(value["database"] == identity["database"] and value["role"] == identity["role"])


def _process(value: Any) -> None:
    _keys(value, {"pid", "start_ticks", "pidfd_owned"})
    _integer(value["pid"], 1, 2**31 - 1)
    _integer(value["start_ticks"], 1)
    _require(type(value["pidfd_owned"]) is bool)


def parse_process_identity(raw: bytes, expected_pid: int) -> dict[str, int]:
    """Parse supplied proc stat bytes only; never read or signal a process."""
    _integer(expected_pid, 1, 2**31 - 1)
    _require(type(raw) is bytes and 0 < len(raw) <= 4096)
    opening = raw.find(b" (")
    closing = raw.rfind(b") ")
    _require(opening > 0 and closing > opening + 1)
    prefix = raw[:opening]
    _require(re.fullmatch(rb"[1-9][0-9]{0,9}", prefix) is not None)
    pid = int(prefix)
    _require(pid == expected_pid)
    fields = raw[closing + 2 :].split()
    _require(len(fields) >= 20 and fields[0] in tuple(bytes([s]) for s in b"RSDZTWtXxKWPIN"))
    _require(all(re.fullmatch(rb"-?[0-9]{1,19}", field) is not None for field in fields[1:20]))
    ticks = int(fields[19])
    _integer(ticks, 1)
    return {"pid": pid, "start_ticks": ticks}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value = {}
    for key, item in pairs:
        _require(key not in value)
        value[key] = item
    return value


def _number(token: str) -> int:
    _require(len(token.removeprefix("-")) <= 19)
    return int(token)


def _reject_number(_: str) -> NoReturn:
    raise OwnershipEvidenceError() from None


def _decode(raw: bytes, limit: int) -> dict[str, Any]:
    _require(type(raw) is bytes and 0 < len(raw) <= limit)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=_number,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise OwnershipEvidenceError() from None
    _require(type(value) is dict)
    return cast(dict[str, Any], value)


def decode_frame(raw: bytes, identity: dict[str, object]) -> dict[str, object]:
    _require(type(raw) is bytes and 4 < len(raw) <= 4096)
    _require(int.from_bytes(raw[:4], "big") == len(raw) - 4)
    value = _decode(raw[4:], 4092)
    _keys(value, {"schema", "kind", "identity", "sender", "case", "sequence", "event", "payload"})
    _integer(value["schema"], 1, 1)
    _require(value["kind"] == "ocwp.ownership.frame")
    _identity(value["identity"], identity)
    _require(value["sender"] in ("host", "owner", "child", "observer"))
    _require(value["case"] in ("setup", "H", "S", "teardown"))
    _integer(value["sequence"], 1, 520)
    event, sender, case, payload = value["event"], value["sender"], value["case"], value["payload"]
    if event == "RESERVED":
        _require(sender in ("observer", "owner") and case == "setup")
        _keys(payload, {"read_only", "transaction_idle"})
        _require(payload["read_only"] is True and payload["transaction_idle"] is True)
    elif event == "BEGIN":
        _require(sender == "owner" and case == "setup")
        _keys(payload, {"experiment_deadline_ns"})
        _integer(payload["experiment_deadline_ns"], 1)
    elif event == "GO":
        _require(sender == "host" and case == "setup")
        _keys(payload, set())
    elif event in ("READY", "OBSERVE", "OBSERVED"):
        _require(case in ("H", "S"))
        expected_sender = {"READY": "child", "OBSERVE": "owner", "OBSERVED": "observer"}[event]
        _require(sender == expected_sender)
        extra = {
            "READY": set(FLAGS),
            "OBSERVE": set(),
            "OBSERVED": {"present", "read_only", "transaction_idle"},
        }[event]
        _keys(payload, {"backend"} | extra)
        _backend(payload["backend"], identity)
        for flag in extra - {"present"}:
            _require(payload[flag] is True)
        if event == "OBSERVED":
            _require(type(payload["present"]) is bool)
    elif event == "CLOSE":
        _require(sender == "owner" and case in ("H", "teardown"))
        _keys(payload, set())
    elif event == "CLOSED":
        _require((sender, case) in (("child", "H"), ("observer", "teardown")))
        _keys(payload, set())
    elif event == "RESULT":
        _require(sender == "owner" and case == "teardown")
        validate_observation(payload, identity)
    elif event == "FAIL":
        _keys(payload, {"code"})
        _require(type(payload["code"]) is str and payload["code"] in CODES)
    else:
        raise OwnershipEvidenceError() from None
    return value


def _case(value: Any, name: str, identity: dict[str, object]) -> None:
    _keys(value, {"name", "status", "backend", "process", *TIMES, *FLAGS})
    _require(value["name"] == name and value["status"] in ("passed", "failed", "skipped"))
    for flag in FLAGS:
        _require(type(value[flag]) is bool)
    for field in TIMES:
        if value[field] is not None:
            _integer(value[field])
    if value["backend"] is not None:
        _backend(value["backend"], identity)
    if value["process"] is not None:
        _process(value["process"])
    if value["status"] == "skipped":
        _require(
            value["backend"] is None
            and value["process"] is None
            and all(value[k] is None for k in TIMES)
            and not any(value[k] for k in FLAGS)
        )
    if value["status"] != "passed":
        return
    _require(
        value["backend"] is not None
        and value["process"] is not None
        and value["process"]["pidfd_owned"] is True
        and all(value[k] is not None for k in TIMES)
        and all(value[k] is True for k in FLAGS)
    )
    start, ready, stop, reap, absent = (value[k] for k in TIMES)
    deadline = start + 8 * SECOND
    end = deadline if name == "H" else deadline + 5 * SECOND
    _require(start <= ready <= stop <= reap <= end and stop <= absent <= end)
    if name == "S":
        _require(ready < deadline <= stop)


def validate_observation(value: Any, identity: dict[str, object]) -> None:
    """Validate owner claims only; no invented resource or container cleanup facts."""
    _keys(value, {"status", "failure", "setup_ns", "elapsed_ns", "observer", "cases"})
    _require(value["status"] in ("observed", "failed"))
    _integer(value["setup_ns"])
    _integer(value["elapsed_ns"])
    observer = value["observer"]
    observer_flags = ("reserved", "read_only", "transaction_idle", "closed", "reaped")
    observer_times = ("reserved_setup_ns", "closed_ns", "reaped_ns")
    _keys(observer, {*observer_flags, *observer_times, "process"})
    _require(all(type(observer[flag]) is bool for flag in observer_flags))
    if observer["process"] is not None:
        _process(observer["process"])
    for field in observer_times:
        if observer[field] is not None:
            _integer(observer[field])
    if observer["reserved"]:
        _require(
            observer["process"] is not None
            and observer["process"]["pidfd_owned"] is True
            and observer["reserved_setup_ns"] is not None
            and observer["read_only"] is True
            and observer["transaction_idle"] is True
        )
    if observer["closed"]:
        _require(observer["process"] is not None and observer["closed_ns"] is not None)
    if observer["reaped"]:
        _require(
            observer["closed"]
            and observer["reaped_ns"] is not None
            and observer["closed_ns"] <= observer["reaped_ns"]
        )

    cases = value["cases"]
    _require(type(cases) is list and len(cases) == 2)
    for case, name in zip(cases, ("H", "S"), strict=True):
        _case(case, name, identity)
    if cases[0]["status"] != "passed":
        _require(cases[1]["status"] == "skipped")
    if all(case["status"] == "passed" for case in cases):
        _require(cases[0]["backend"] != cases[1]["backend"])
        _require(
            (cases[0]["process"]["pid"], cases[0]["process"]["start_ticks"])
            != (cases[1]["process"]["pid"], cases[1]["process"]["start_ticks"])
        )
    if cases[1]["start_ns"] is not None:
        _require(cases[0]["status"] == "passed")
        _require(cases[1]["start_ns"] >= max(cases[0]["reaped_ns"], cases[0]["absent_ns"]))
    if value["status"] == "failed":
        _require(type(value["failure"]) is str and value["failure"] in CODES)
        return
    _require(value["failure"] is None and all(c["status"] == "passed" for c in cases))
    _require(value["setup_ns"] <= 65 * SECOND and value["elapsed_ns"] <= 26 * SECOND)
    _require(all(observer[flag] for flag in observer_flags))
    _require(
        observer["reserved_setup_ns"] <= value["setup_ns"]
        and observer["reaped_ns"] <= value["elapsed_ns"]
    )
    _require(
        all(max(case["reaped_ns"], case["absent_ns"]) <= observer["closed_ns"] for case in cases)
    )
    _require(
        all(
            (case["process"]["pid"], case["process"]["start_ticks"])
            != (observer["process"]["pid"], observer["process"]["start_ticks"])
            for case in cases
        )
    )
    _require(all(case[t] <= value["elapsed_ns"] for case in cases for t in TIMES))


def validate_receipt(value: Any, identity: dict[str, object]) -> None:
    _require(type(value) is dict)
    schema = value.get("schema")
    _integer(schema, 1, 2)
    _keys(
        value,
        {
            "schema",
            "kind",
            "identity",
            "status",
            "failure",
            "setup_ns",
            "elapsed_ns",
            "observer",
            "cases",
            "resources",
            "primary_cleanup",
            "independent_cleanup",
        }
        | ({"owner_observation"} if schema == 2 else set()),
    )
    _require(value["kind"] == "ocwp.quote_ownership.receipt")
    _identity(value["identity"], identity)
    _require(value["status"] in ("passed", "pending_cleanup", "failed"))
    for field in ("primary_cleanup", "independent_cleanup"):
        _require(value[field] in ("pending", "verified_absent", "unknown"))
    if schema == 2:
        _require(value["owner_observation"] in ("accepted", "unavailable"))
        if value["owner_observation"] == "unavailable":
            _require(value["status"] == "failed")
            _require(type(value["failure"]) is str and value["failure"] in CODES)
            _require(
                all(
                    value[key] is None
                    for key in ("setup_ns", "elapsed_ns", "observer", "resources")
                )
            )
            _require(
                value["cases"]
                == [{"name": "H", "status": "unknown"}, {"name": "S", "status": "unknown"}]
            )
            return
    validate_observation(
        {
            "status": "failed" if value["status"] == "failed" else "observed",
            **{k: value[k] for k in ("failure", "setup_ns", "elapsed_ns", "observer", "cases")},
        },
        identity,
    )
    resources = value["resources"]
    _keys(
        resources,
        {
            "worker_peak_bytes",
            "pg_peak_bytes",
            "worker_processes",
            "pg_processes",
            "pressure_events",
        },
    )
    for number in resources.values():
        _integer(number)
    for field in ("primary_cleanup", "independent_cleanup"):
        _require(value[field] in ("pending", "verified_absent", "unknown"))
    if value["status"] == "failed":
        return
    _require(
        resources["worker_peak_bytes"] <= 768 * 1024**2
        and resources["pg_peak_bytes"] <= 1024 * 1024**2
        and 1 <= resources["worker_processes"] <= 64
        and 1 <= resources["pg_processes"] <= 128
        and resources["pressure_events"] == 0
    )
    _require(value["primary_cleanup"] == "verified_absent")
    if value["status"] == "passed":
        _require(value["independent_cleanup"] == "verified_absent")
    else:
        _require(value["independent_cleanup"] == "pending")


def validate_current_receipt(value: Any, identity: dict[str, object]) -> None:
    """Current writer/sealer/stager cannot promote historical schema1 evidence."""
    validate_receipt(value, identity)
    _require(value["schema"] == 2)


def encode_receipt(value: dict[str, object], identity: dict[str, object]) -> bytes:
    try:
        validate_receipt(value, identity)
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()
        _require(len(raw) <= 16384)
        return raw
    except (TypeError, ValueError, RecursionError):
        raise OwnershipEvidenceError() from None


def decode_receipt(raw: bytes, identity: dict[str, object]) -> dict[str, object]:
    value = _decode(raw, 16384)
    try:
        validate_receipt(value, identity)
    except (TypeError, ValueError, RecursionError):
        raise OwnershipEvidenceError() from None
    return value


class MeasurementGate:
    """Pure clock/order gate for the planned owner, not process/cleanup evidence."""

    def __init__(self, setup_started_ns: int) -> None:
        _integer(setup_started_ns)
        self.last = setup_started_ns
        self.setup_end = setup_started_ns + 65 * SECOND
        self.experiment_end: int | None = None
        self.case_deadline: int | None = None
        self.state = "setup"

    def _check(self, now: int, allowed: set[str]) -> None:
        try:
            _integer(now)
            _require(now >= self.last and self.state in allowed)
            end = self.setup_end if self.experiment_end is None else self.experiment_end
            _require(now <= end)
            self.last = now
        except OwnershipEvidenceError:
            self.state = "failed"
            raise

    def reserve(self, now_ns: int) -> None:
        self._check(now_ns, {"setup"})
        self.state = "reserved"

    def go(self, now_ns: int) -> None:
        self._check(now_ns, {"reserved"})
        self.experiment_end = now_ns + 26 * SECOND
        self.state = "go"

    def admit(self, case: str, now_ns: int) -> int:
        expected = "go" if case == "H" else "H_done" if case == "S" else "invalid"
        self._check(now_ns, {expected})
        self.case_deadline = now_ns + 8 * SECOND
        self.state = case
        return self.case_deadline

    def finish(self, case: str, passed: bool, now_ns: int) -> None:
        self._check(now_ns, {case} if case in ("H", "S") else set())
        if type(passed) is not bool or not passed:
            self.state = "failed"
            if type(passed) is not bool:
                raise OwnershipEvidenceError() from None
            return
        _require(self.case_deadline is not None)
        deadline = cast(int, self.case_deadline)
        end = deadline + (5 * SECOND if case == "S" else 0)
        if now_ns > end or (case == "S" and now_ns < deadline):
            self.state = "failed"
            raise OwnershipEvidenceError() from None
        self.state = case + "_done"

    def close_observer(self, now_ns: int) -> None:
        self._check(now_ns, {"S_done", "failed"})
        self.state = "closed"


class FrameStream:
    """Pure sequence/identity gate attached to one future owned IPC pipe."""

    def __init__(
        self,
        identity: dict[str, object],
        sender: str,
        case: str,
        *,
        backend: dict[str, object] | None = None,
    ) -> None:
        _identity(identity, identity)
        _require(sender in ("host", "owner", "child", "observer"))
        _require(case in ("setup", "H", "S", "teardown"))
        if backend is not None:
            _backend(backend, identity)
        if sender == "observer" and case in ("H", "S"):
            _require(backend is not None)
        self.identity = dict(identity)
        self.sender = sender
        self.case = case
        self.backend = None if backend is None else dict(backend)
        self.sequence = 0
        self.counts: dict[str, int] = {}
        self.failed = False

    def accept(self, raw: bytes) -> dict[str, object]:
        try:
            _require(not self.failed)
            value: dict[str, Any] = decode_frame(raw, self.identity)
            _require(value["sender"] == self.sender and value["case"] == self.case)
            _require(value["sequence"] == self.sequence + 1)
            event = value["event"]
            if self.sender == "child" and event == "CLOSED":
                _require(self.counts.get("READY", 0) == 1)
            count = self.counts.get(event, 0) + 1
            _require(count <= (256 if event in ("OBSERVE", "OBSERVED") else 1))
            observed = value["payload"].get("backend")
            if observed is not None and self.backend is not None:
                _require(observed == self.backend)
            self.sequence = value["sequence"]
            self.counts[event] = count
            if event in ("FAIL", "CLOSED", "RESULT"):
                self.failed = True
            return value
        except OwnershipEvidenceError:
            self.failed = True
            raise


def identity_from_environment(env: dict[str, str]) -> dict[str, object]:
    """Pure expected binding; fresh API guard/readbacks remain separately required."""
    try:
        fixed = {
            "GITHUB_REPOSITORY": "IzignaMx/open-cycling-workshop",
            "GITHUB_REPOSITORY_ID": "1327018760",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_NUMBER": "1",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        _require(all(env.get(k) == v for k, v in fixed.items()))
        _require(env["GITHUB_SHA"] == env["OCWP_EXPECTED_SOURCE_SHA"])
        value: dict[str, object] = {
            "commit": env["GITHUB_SHA"],
            "tree": env["OCWP_EXPECTED_TREE_SHA"],
            "worker_image": env["OCWP_OWNERSHIP_WORKER_IMAGE_ID"],
            "pg_image": env["OCWP_OWNERSHIP_PG_IMAGE_ID"],
            "authorization": PUBLIC_PROPOSAL_SHA256,
            "nonce": env["OCWP_OWNERSHIP_NONCE"],
            "run_id": env["GITHUB_RUN_ID"],
            "workflow_id": env["OCWP_EXPECTED_WORKFLOW_ID"],
            "run_number": 1,
            "run_attempt": 1,
            "repository": fixed["GITHUB_REPOSITORY"],
            "repository_id": 1327018760,
            "workflow_path": ".github/workflows/quote-ownership-measurement.yml",
            "ref": fixed["GITHUB_REF"],
            "database": "ocwp",
            "role": "ocwp",
        }
        _identity(value, value)
        return value
    except (ValueError, KeyError, TypeError):
        raise OwnershipEvidenceError() from None


def validate_cleanup(value: Any, identity: dict[str, object] | None) -> None:
    _keys(
        value,
        {
            "schema",
            "kind",
            "identity",
            "expected_commit",
            "run_id",
            "run_attempt",
            "owner_manifest_present",
            "owner_token",
            "outcome",
            "elapsed_ns",
            "receipt_sha256",
        },
    )
    _integer(value["schema"], 1, 1)
    _require(value["kind"] == "ocwp.quote_ownership.independent_cleanup")
    _matches(value["expected_commit"], r"[0-9a-f]{40}")
    _matches(value["run_id"], r"[1-9][0-9]{0,19}")
    _integer(value["run_attempt"], 1, 2**31 - 1)
    _integer(value["elapsed_ns"])
    _require(type(value["owner_manifest_present"]) is bool)
    _require(value["outcome"] in ("verified_absent", "not_started", "unknown"))
    if value["receipt_sha256"] is not None:
        _matches(value["receipt_sha256"], r"[0-9a-f]{64}")
    if value["owner_token"] is not None:
        _matches(value["owner_token"], r"[0-9a-f]{32}")
    if identity is not None:
        _identity(value["identity"], identity)
        _require(
            value["expected_commit"] == identity["commit"]
            and value["run_id"] == identity["run_id"]
            and value["run_attempt"] == identity["run_attempt"]
        )
    else:
        _require(value["identity"] is None and value["outcome"] != "verified_absent")
    if value["outcome"] == "verified_absent":
        _require(
            identity is not None
            and value["owner_manifest_present"] is True
            and value["owner_token"] == identity["nonce"]
            and value["elapsed_ns"] <= 55 * SECOND
        )
    if value["outcome"] == "not_started":
        _require(value["owner_manifest_present"] is False and value["owner_token"] is None)


def validate_fixture_preparation(value: Any, identity: dict[str, object]) -> None:
    _keys(value, {"schema", "kind", "identity", "pg_base_image", "pg_base_reference", "files"})
    _integer(value["schema"], 1, 1)
    _require(value["kind"] == "ocwp.quote_ownership.fixture_preparation")
    _identity(value["identity"], identity)
    _matches(value["pg_base_image"], r"sha256:[0-9a-f]{64}")
    _matches(value["pg_base_reference"], r"postgres@sha256:[0-9a-f]{64}")
    _keys(value["files"], {"dockerfile", "initializer", "public_fixture"})
    for digest in value["files"].values():
        _matches(digest, r"[0-9a-f]{64}")
