from pathlib import Path


def test_generated_typescript_client_contains_v01_customer_and_sync_contracts() -> None:
    generated = Path("packages/api-client/src/generated.ts").read_text()
    client = Path("packages/api-client/src/client.ts").read_text()

    for symbol in (
        "CustomerCreateRequest",
        "CustomerResponse",
        "MutationRequest",
        "PushMutationsResponse",
        "ChangePageResponse",
    ):
        assert f"export interface {symbol}" in generated
    assert "createCustomer" in client
    assert "pushMutations" in client
    assert "pullChanges" in client


def test_context_contract_preserves_literals_and_closed_nullable_schema() -> None:
    import json

    generated = Path("packages/api-client/src/generated.ts").read_text()
    openapi = json.loads(Path("packages/api-client/openapi.json").read_text())
    context = openapi["components"]["schemas"]["AccessContextResponse"]
    principal = openapi["components"]["schemas"]["ContextPrincipal"]
    assert context["additionalProperties"] is False
    assert principal["additionalProperties"] is False
    assert context["properties"]["protocol"]["const"] == 1
    assert context["properties"]["snapshot_protocol"]["anyOf"] == [
        {"const": "baseline-v1", "type": "string"},
        {"type": "null"},
    ]
    assert context["properties"]["dataset_incarnation"]["type"] == "string"
    assert set(context["required"]) == set(context["properties"])
    assert "  protocol: 1\n" in generated
    assert '  policy_revision: "ocwp-access-baseline-2"\n' in generated
    assert '  snapshot_protocol: "baseline-v1" | null\n' in generated
    assert "  dataset_incarnation: string\n" in generated
