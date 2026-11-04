from datetime import UTC, datetime

import pytest
from cycling_workshop.bicycles.domain import Bicycle


def _create(**overrides) -> Bicycle:
    payload = {
        "bicycle_id": "0198-bike",
        "customer_id": "0198-customer",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "brand": "  Trek   Marlin  ",
        "model": " 7   ",
    }
    payload.update(overrides)
    return Bicycle.create(**payload)


def test_bicycle_create_normalizes_brand_and_model() -> None:
    now = datetime(2026, 8, 31, tzinfo=UTC)
    bicycle = _create(model="  Marlin   7 ", now=now)

    assert bicycle.brand == "Trek Marlin"
    assert bicycle.model == "Marlin 7"
    assert bicycle.customer_id == "0198-customer"
    assert bicycle.organization_id == "org-1"
    assert bicycle.location_id == "loc-1"
    assert bicycle.created_at == now
    assert bicycle.updated_at == now
    assert bicycle.version == 1


def test_bicycle_rejects_blank_brand() -> None:
    with pytest.raises(ValueError, match="brand"):
        _create(brand="    ")


def test_bicycle_blank_optional_fields_become_none() -> None:
    bicycle = _create(model="   ", bicycle_type="  ", wheel_size="  ", notes="  ")

    assert bicycle.model is None
    assert bicycle.bicycle_type is None
    assert bicycle.wheel_size is None
    assert bicycle.notes is None


def test_bicycle_requires_customer_and_tenant_scope() -> None:
    with pytest.raises(ValueError, match="customer_id"):
        _create(customer_id="   ")
    with pytest.raises(ValueError, match="organization_id"):
        _create(organization_id="")
    with pytest.raises(ValueError, match="location_id"):
        _create(location_id="  ")


def test_bicycle_update_bumps_version_and_normalizes() -> None:
    bicycle = _create()
    later = datetime(2026, 9, 1, tzinfo=UTC)

    updated = bicycle.update(brand="  Giant ", notes=" roda 29 ", now=later)

    assert updated.brand == "Giant"
    assert updated.notes == "roda 29"
    assert updated.version == bicycle.version + 1
    assert updated.updated_at == later
    assert updated.created_at == bicycle.created_at
    # immutable identity
    assert updated.bicycle_id == bicycle.bicycle_id
    assert updated.customer_id == bicycle.customer_id


@pytest.mark.parametrize(
    "field,limit",
    [("brand", 120), ("model", 120), ("bicycle_type", 60), ("wheel_size", 30), ("notes", 2000)],
)
@pytest.mark.parametrize("character", ["x", "🚲"])
def test_bicycle_normalized_storage_limits(field, limit, character):
    value = character * limit
    assert getattr(_create(**{field: "  " + value + "  "}), field) == value
    assert getattr(_create().update(**{field: value}), field) == value
    with pytest.raises(ValueError):
        _create(**{field: value + character})
    with pytest.raises(ValueError):
        _create().update(**{field: value + character})


@pytest.mark.parametrize("field", ["brand", "model", "bicycle_type", "wheel_size", "notes"])
@pytest.mark.parametrize("value", [12, False, {}, []])
def test_bicycle_supplied_types_are_not_coerced(field, value):
    with pytest.raises(ValueError):
        _create(**{field: value})
    original = _create()
    with pytest.raises(ValueError):
        original.update(**{field: value})
    assert original.version == 1


def test_bicycle_null_brand_rejected_optional_null_and_omission_retained():
    with pytest.raises(ValueError):
        _create().update(brand=None)
    original = _create(model="Known", notes="Keep")
    changed = original.update(model=None)
    assert changed.model is None and changed.notes == "Keep"
