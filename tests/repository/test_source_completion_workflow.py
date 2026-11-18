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
