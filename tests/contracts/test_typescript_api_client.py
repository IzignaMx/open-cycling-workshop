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
