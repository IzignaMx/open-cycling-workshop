import uuid
from datetime import UTC, datetime

import pytest
from cycling_workshop.customers.domain import Customer
from cycling_workshop.shared.ids import new_id


def test_new_id_is_uuidv7_compatible_and_lexically_monotonic() -> None:
    values = [new_id() for _ in range(50)]
    parsed = [uuid.UUID(value) for value in values]

    assert all(item.version == 7 for item in parsed)
    assert all(item.variant == uuid.RFC_4122 for item in parsed)
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_customer_create_normalizes_required_name() -> None:
    now = datetime(2026, 8, 7, tzinfo=UTC)
    customer = Customer.create(
        customer_id="0198-irrelevant",
        organization_id="org-1",
        location_id="loc-1",
        display_name="  Ana   Rivera  ",
        email=" ANA@example.com ",
        phone=" 5512345678 ",
        now=now,
    )

    assert customer.display_name == "Ana Rivera"
    assert customer.email == "ana@example.com"
    assert customer.phone == "5512345678"
    assert customer.created_at == now
    assert customer.updated_at == now
    assert customer.version == 1


def test_customer_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="display_name"):
        Customer.create(
            customer_id="customer-1",
            organization_id="org-1",
            location_id="loc-1",
            display_name="   ",
        )


def test_customer_mutations_increment_version_and_preserve_identity() -> None:
    customer = Customer.create(
        customer_id="customer-1",
        organization_id="org-1",
        location_id="loc-1",
        display_name="Ana",
    )

    renamed = customer.rename("Ana Rivera")
    changed = renamed.change_contact(email="ana@bike.example", phone=None)

    assert renamed.customer_id == customer.customer_id
    assert renamed.version == 2
    assert changed.version == 3
    assert changed.display_name == "Ana Rivera"
    assert changed.email == "ana@bike.example"
    assert changed.phone is None


def test_customer_update_applies_multiple_fields_as_one_versioned_mutation() -> None:
    customer = Customer.create(
        customer_id="customer-1",
        organization_id="org-1",
        location_id="loc-1",
        display_name="Ana",
        email="ana@old.example",
    )

    updated = customer.update(
        display_name="Ana Rivera",
        email="ana@new.example",
        phone="5512345678",
    )

    assert updated.display_name == "Ana Rivera"
    assert updated.email == "ana@new.example"
    assert updated.phone == "5512345678"
    assert updated.version == 2


def test_customer_partial_update_preserves_omitted_contact_fields() -> None:
    customer = Customer.create(
        customer_id="customer-1",
        organization_id="org-1",
        location_id="loc-1",
        display_name="Ana",
        email="ana@example.com",
        phone="5512345678",
    )

    updated = customer.update(display_name="Ana Rivera")

    assert updated.email == "ana@example.com"
    assert updated.phone == "5512345678"
    assert updated.version == 2
