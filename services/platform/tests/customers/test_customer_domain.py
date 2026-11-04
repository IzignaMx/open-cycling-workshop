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


@pytest.mark.parametrize(
    "field,value",
    [
        ("display_name", "x" * 201),
        ("email", "a" * 315 + "@x.com"),
        ("phone", "1" * 65),
        ("email", "İ" * 158 + "@x.co"),
        ("display_name", "🚲" * 201),
        ("display_name", "e\u0301" * 101),
    ],
)
def test_customer_rejects_normalized_storage_overflow_without_mutating_original(field, value):
    original = Customer.create(
        customer_id="public-customer",
        organization_id="org-1",
        location_id="loc-1",
        display_name="Original",
    )
    with pytest.raises(ValueError, match=field):
        Customer.create(
            customer_id="new",
            organization_id="org-1",
            location_id="loc-1",
            **{"display_name": "Public", field: value},
        )
    with pytest.raises(ValueError, match=field):
        original.update(**{field: value})
    if field == "display_name":
        with pytest.raises(ValueError, match=field):
            original.rename(value)
    else:
        with pytest.raises(ValueError, match=field):
            original.change_contact(**{"email": None, "phone": None, field: value})
    assert original.display_name == "Original" and original.version == 1
    assert original.email is None and original.phone is None


@pytest.mark.parametrize(
    "name,email,phone",
    [
        ("🚲" * 200, "a" * 314 + "@x.com", "1" * 64),
        ("e\u0301" * 100, "İ" * 157 + "a@x.co", "☎" * 64),
        ("  " + "n" * 200 + "  ", "  " + "a" * 314 + "@x.com  ", " " + "1 " * 64),
    ],
)
def test_customer_storage_caps_count_normalized_codepoints_without_truncation(name, email, phone):
    customer = Customer.create(
        customer_id="public-customer",
        organization_id="org-1",
        location_id="loc-1",
        display_name=name,
        email=email,
        phone=phone,
    )
    assert customer.display_name == " ".join(name.split())
    assert customer.email == email.strip().lower()
    assert customer.phone == "".join(phone.split())
    assert len(customer.display_name) == 200
    assert len(customer.email) == 320
    assert len(customer.phone) == 64


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize(
    "field,value",
    [("display_name", None)]
    + [
        (field, value)
        for field in ("display_name", "email", "phone")
        for value in (123, True, {"public": "canary"}, [])
    ],
)
def test_customer_rejects_malformed_supplied_field_types_without_coercion(operation, field, value):
    original = Customer.create(
        customer_id="public-customer",
        organization_id="org-1",
        location_id="loc-1",
        display_name="Original",
        email="public@example.test",
        phone="123",
    )
    with pytest.raises(ValueError, match=field):
        if operation == "create":
            Customer.create(
                customer_id="new",
                organization_id="org-1",
                location_id="loc-1",
                **{"display_name": "Public", field: value},
            )
        else:
            original.update(**{field: value})
    if operation == "update":
        with pytest.raises(ValueError, match=field):
            if field == "display_name":
                original.rename(value)
            else:
                original.change_contact(**{"email": None, "phone": None, field: value})
    assert (original.display_name, original.email, original.phone, original.version) == (
        "Original",
        "public@example.test",
        "123",
        1,
    )


def test_customer_null_clears_contacts_and_omission_preserves_existing_contacts():
    original = Customer.create(
        customer_id="public-customer",
        organization_id="org-1",
        location_id="loc-1",
        display_name="Public",
        email="public@example.test",
        phone="123",
    )
    unchanged = original.update(display_name="Renamed")
    assert (unchanged.email, unchanged.phone) == (original.email, original.phone)
    email_cleared = unchanged.update(email=None)
    assert email_cleared.email is None and email_cleared.phone == "123"
    cleared = unchanged.update(email=None, phone=None)
    assert cleared.email is None and cleared.phone is None
    assert (cleared.display_name, cleared.version) == ("Renamed", 3)
