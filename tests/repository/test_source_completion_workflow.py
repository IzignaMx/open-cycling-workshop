"""Authoring guardrails only; native execution is independently required."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "apps/web/e2e/source-completion-new-work.spec.ts"


def test_source_completion_is_observed_before_destination_authoring() -> None:
    text = SPEC.read_text()
    markers = [
        "const unsent = await captureSnapshot(source)",
        "expect(restored).toEqual(unsent)",
        "const sourceOrder = await appliedOrder(source, sourceProblem)",
        "await assertServerOrder(sourceOrder.entityId, sourceProblem)",
        "const destinationBefore = await kernelSnapshot(destination)",
        "expect(destinationBefore.journal).toEqual([])",
        "await fillIntake(destination, customer.entityId, destinationProblem, false)",
        "const destinationOrder = await appliedOrder(destination, destinationProblem)",
        "expect(destinationOrder.entityId).not.toBe(sourceOrder.entityId)",
        "expect(sourceAfter.journal).toEqual(sourceCompleted.journal)",
    ]
    positions = [text.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert "test.use({ trace: 'on' })" in text
    assert "source-completion-new-work-receipt" in text
    assert "context.newPage()" in text
    assert "destinationContext" not in text
    assert "setOffline" not in text


def test_destination_preview_is_loopback_same_build_without_reusing_server() -> None:
    text = (ROOT / "apps/web/playwright.config.ts").read_text()
    assert "preview --host 127.0.0.1 --port 5175" in text
    assert "url: 'http://127.0.0.1:5175'" in text
    assert "reuseExistingServer: false" in text
    assert (
        "e2e/source-completion-new-work.spec.ts"
        in (ROOT / "apps/web/tsconfig.e2e-orders.json").read_text()
    )


def test_destination_session_is_observed_not_copied_and_realms_are_distinct() -> None:
    text = SPEC.read_text()
    for marker in (
        "destination.waitForResponse",
        "expect(loginResponse.status()).toBe(200)",
        "expect(destinationToken === issued.access_token).toBe(true)",
        "expect(destinationToken !== token).toBe(true)",
        "await assertServerContext(source, token)",
        "await assertServerContext(destination, destinationToken)",
        "expect(server.dataset_incarnation).toBe(local.datasetIncarnation)",
        "expect(server.authorization_epoch).toBe(local.authorizationEpoch)",
        "expect(destinationBefore.context.principal.apiRealm).not.toBe(",
    ):
        assert marker in text
    assert "sessionStorage.setItem" not in text
    assert "addCookies" not in text


def test_reception_measurement_keeps_failed_attempts_and_physical_gate_open() -> None:
    text = (ROOT / "apps/web/e2e/reception-phase-measurement.spec.ts").read_text()
    assert "test.describe.configure({ retries: 0 })" in text
    assert "test.use({ trace: 'on' })" in text
    assert "for (let trial = 1; trial <= 3; trial += 1)" in text
    assert text.index("phases.localCommit = phaseDuration") < text.index(
        "getByText('Orden guardada localmente'"
    )
    assert "phaseDuration(submitStart, performance.now())" in text
    assert "status: 'failed'" in text
    assert "'reception-attempts-raw'" in text
    assert "'reception-phase-measurement'" in text
    assert "expect(changes.has_more).toBe(false)" in text
    assert "expect(changes.items).toHaveLength(7)" in text
    document = (
        ROOT / "docs/10-spec-development/2026-11-19-reception-phase-measurement.md"
    ).read_text()
    for marker in (
        "hosted native measurement qualified on main; physical acceptance remains open",
        "44472900336",
        "not a cold",
        "not zero durations",
        "G1\u2013G6",
        "BLOCKED",
    ):
        assert marker in document
    runner = (ROOT / "apps/web/tools/run-core-tests.mjs").read_text()
    assert "'tsconfig.reception-measurement.json'" in runner
    assert "'tests/pwa/reception-measurement.test.mjs'" in runner
