"""No Docker or quote construction: fixed profile control-contract tests."""

import json
from pathlib import Path

import pytest
from test_quote_capacity_micro import module


def profile_value(completed=6):
    actions = ("create", "revise", "revise", "revise", "fresh_load", "exact_retry")
    rows = []
    for ordinal, action in enumerate(actions[:completed], 1):
        n = min(ordinal, 4)
        rows.append(
            dict(
                ordinal=ordinal,
                action=action,
                wall_seconds=0.1,
                process_cpu_seconds=0.000001,
                **{
                    k: dict(calls=1, seconds=0.01)
                    for k in ("candidate", "reconstruction", "commit", "sql")
                },
                functions={
                    k: (
                        None
                        if ordinal == 1 and k in {"reconstruct", "row_assembly"}
                        else dict(
                            primitive_calls=1,
                            total_calls=1,
                            own_seconds=0.001,
                            cumulative_seconds=0.005,
                        )
                    )
                    for k in (
                        "reconstruct",
                        "row_assembly",
                        "canonical_json",
                        "quote_codec",
                        "command_proof",
                    )
                },
                raw_request_bytes=100 if ordinal <= 4 else None,
                logical_bytes=200 if ordinal <= 4 else None,
                history_bytes=201 * n + 1,
                revisions=n,
                receipts=n,
                counts=[1, n, n, n],
            )
        )
        rows[-1]["candidate"] = dict(calls=int(ordinal <= 4), seconds=0.01 if ordinal <= 4 else 0.0)
        rows[-1]["reconstruction"] = dict(
            calls=int(ordinal > 1), seconds=0.01 if ordinal > 1 else 0.0
        )
        rows[-1]["sql"]["verbs"] = dict(SELECT=1, INSERT=0, UPDATE=0, DELETE=0, OTHER=0)
    return dict(
        schema=1,
        active_ordinal=None if completed == 6 else completed + 1,
        complete=completed == 6,
        process_cpu_seconds=0.00001 if completed == 6 else None,
        records=rows,
    )


def test_fixed_profile_closed_schema_and_contiguous_prefix():
    value = profile_value()
    assert module.profile_result(json.dumps(value), final=True) == value
    partial = profile_value(2)
    assert module.profile_result(json.dumps(partial)) == partial
    assert module.profile_observation(partial, value) == value
    assert module.profile_observation(partial, partial) == partial
    assert len(json.dumps(value).encode()) < module.LIMIT


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(extra="private"),
        lambda v: v.update(process_cpu_seconds=float("nan")),
        lambda v: v["records"][0].update(ordinal=True),
        lambda v: v["records"][1].update(ordinal=1),
        lambda v: v["records"][0].update(wall_seconds=-1),
        lambda v: v["records"][0]["sql"].update(seconds=float("inf")),
        lambda v: v["records"][0]["candidate"].update(calls=True),
        lambda v: v["records"][0]["functions"].update(private=None),
        lambda v: v["records"][0].update(counts=[1, 32, 32, 32]),
        lambda v: v.update(active_ordinal=6),
        lambda v: v["records"][0]["candidate"].update(calls=10**400),
        lambda v: v["records"][0]["candidate"].update(calls=0, seconds=0),
        lambda v: v["records"][1]["functions"].update(reconstruct=None),
        lambda v: v["records"][0]["functions"].update(canonical_json=None),
        lambda v: v["records"][0]["functions"]["quote_codec"].update(own_seconds=0.1),
        lambda v: v["records"][0]["commit"].update(calls=0, seconds=0),
        lambda v: v["records"][0]["sql"]["verbs"].update(OTHER=2),
        lambda v: v["records"][0]["sql"].update(calls=0, seconds=0),
        lambda v: v["records"][0]["sql"]["verbs"].update(PRIVATE=0),
    ],
)
def test_profile_rejects_malformed_or_unbounded_metrics(mutation):
    value = profile_value()
    mutation(value)
    with pytest.raises(module.ProofFailure):
        module.profile_result(json.dumps(value), final=True)


def test_zero_exit_cannot_accept_partial_profile_or_rewrite_prefix():
    with pytest.raises(module.ProofFailure):
        module.profile_result(
            json.dumps(profile_value()).replace('"schema": 1', '"schema": 1, "schema": 1')
        )
    with pytest.raises(module.ProofFailure):
        module.profile_result(json.dumps(profile_value(5)), final=True)
    with pytest.raises(module.ProofFailure):
        module.profile_observation(profile_value(3), profile_value(2))
    previous, current = profile_value(2), profile_value(3)
    current["records"][0]["wall_seconds"] = 0.2
    with pytest.raises(module.ProofFailure):
        module.profile_observation(previous, current)


def test_six_full_metric_rows_fit_existing_output_bound():
    value = profile_value()
    for row in value["records"]:
        for key in row["functions"]:
            if row["functions"][key] is None:
                continue
            row["functions"][key] = dict(
                primitive_calls=1_000_000,
                total_calls=1_000_000,
                own_seconds=0.09999999999999999,
                cumulative_seconds=0.09999999999999999,
            )
    encoded = json.dumps(value)
    assert len(encoded.encode()) < module.LIMIT
    assert module.profile_result(encoded, final=True) == value


def test_whole_profile_report_is_bounded_and_oversize_fails_closed():
    report = dict(
        mode="four_revision_diagnostic",
        status="micro_passed_not_capacity",
        cleanup="verified_absent",
        profile_last_observed=profile_value(),
        commit="a" * 40,
        tree="b" * 40,
    )
    encoded = module.profile_report(report)
    assert len(encoded.encode()) < module.LIMIT
    assert json.loads(encoded) == report
    report["unexpected_large"] = "private" * module.LIMIT
    encoded = module.profile_report(report)
    assert len(encoded.encode()) < module.LIMIT
    assert report["status"] == "failed"
    closed = json.loads(encoded)
    assert closed["failure"] == "profile_evidence_output_limit"
    assert closed["cleanup"] == "verified_absent"
    assert "private" not in encoded


def test_fixed_profile_has_distinct_opened_only_single_job_gate():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/quote-four-revision-profile.yml"
    workflow = path.read_text()
    for required in (
        "types: [opened]",
        "github.head_ref == 'codex/quote-four-revision-profile'",
        "github.run_number == '1' && github.run_attempt == '1'",
        "github.event.pull_request.head.repo.full_name == github.repository",
        "github.repository == 'IzignaMx/open-cycling-workshop'",
        "timeout-minutes: 15",
        "--four-revision-profile",
    ):
        assert required in workflow
    assert "--online-once" not in workflow
    assert workflow.count("runs-on:") == 1


def test_profile_stops_both_exact_containers_before_observing_stop():
    calls = []

    def execute(args, **kwargs):
        calls.append(args)
        return "false" if args[1] == "inspect" else ""

    assert module.stop_profile(["a" * 64, "b" * 64], execute)
    assert [call[1] for call in calls] == ["kill", "kill", "inspect", "inspect"]
    assert [call[-1] for call in calls] == ["b" * 64, "a" * 64] * 2


def test_profile_stop_timeout_is_unverified_and_still_attempts_database():
    calls = []

    def execute(args, **kwargs):
        calls.append(args)
        raise module.ProofFailure("command_timeout")

    assert not module.stop_profile(["a" * 64, "b" * 64], execute)
    assert [call[1] for call in calls] == ["kill", "kill", "inspect", "inspect"]
