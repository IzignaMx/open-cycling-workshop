from datetime import UTC, datetime

import pytest
from cycling_workshop.inventory.domain import (
    InventoryMovement,
    MovementKind,
    Product,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _product(**overrides: object) -> Product:
    payload: dict[str, object] = {
        "product_id": "product-1",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "sku": "  BRK-105 ",
        "name": "  Pastilla de freno   orgánica ",
        "unit": "  pieza ",
    }
    payload.update(overrides)
    return Product.create(**payload)  # type: ignore[arg-type]


def _movement(**overrides: object) -> InventoryMovement:
    payload: dict[str, object] = {
        "movement_id": "movement-1",
        "product_id": "product-1",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "kind": "ADJUST",
        "quantity": 10,
        "order_id": None,
        "reference_movement_id": None,
        "actor_id": "user-1",
        "note": " stock inicial ",
        "now": NOW,
    }
    payload.update(overrides)
    return InventoryMovement.record(**payload)  # type: ignore[arg-type]


def test_product_create_normalizes_fields() -> None:
    product = _product()

    assert product.sku == "BRK-105"
    assert product.name == "Pastilla de freno orgánica"
    assert product.unit == "pieza"
    assert product.version == 1


def test_product_rejects_blank_sku_or_name() -> None:
    with pytest.raises(ValueError, match="sku"):
        _product(sku="   ")
    with pytest.raises(ValueError, match="name"):
        _product(name="")


def test_movement_signs_follow_the_kind_contract() -> None:
    adjust_in = _movement(kind="ADJUST", quantity=10)
    assert adjust_in.quantity == 10

    reserve = _movement(kind="RESERVE", quantity=5, order_id="order-1")
    assert reserve.quantity == -5
    assert reserve.order_id == "order-1"

    release = _movement(
        kind="RELEASE",
        quantity=5,
        order_id="order-1",
        reference_movement_id=reserve.movement_id,
    )
    assert release.quantity == 5

    consume = _movement(
        kind="CONSUME",
        quantity=5,
        order_id="order-1",
        reference_movement_id=reserve.movement_id,
    )
    # Consuming finalizes the hold: the reservation already deducted stock.
    assert consume.quantity == 5


def test_reserve_requires_positive_quantity_and_an_order() -> None:
    with pytest.raises(ValueError, match="positive"):
        _movement(kind="RESERVE", quantity=-5, order_id="order-1")
    with pytest.raises(ValueError, match="order"):
        _movement(kind="RESERVE", quantity=5, order_id=None)


def test_release_and_consume_require_reference_and_cannot_release_twice() -> None:
    reserve = _movement(kind="RESERVE", quantity=5, order_id="order-1")

    with pytest.raises(ValueError, match="reference"):
        _movement(kind="RELEASE", quantity=5, order_id="order-1")

    release = _movement(
        kind="RELEASE", quantity=5, order_id="order-1", reference_movement_id=reserve.movement_id
    )
    # A second release against the same reservation is rejected at the domain
    # level when the caller marks the reservation consumed beforehand.
    with pytest.raises(ValueError, match="already released"):
        _movement(
            kind="RELEASE",
            quantity=5,
            order_id="order-1",
            reference_movement_id=reserve.movement_id,
            previously_released=[release.movement_id],
        )


def test_consume_requires_reference_to_a_reservation() -> None:
    with pytest.raises(ValueError, match="reference"):
        _movement(kind="CONSUME", quantity=5, order_id="order-1")


def test_unknown_kind_and_zero_quantity_are_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        _movement(kind="STEAL", quantity=1)
    with pytest.raises(ValueError, match="zero"):
        _movement(kind="ADJUST", quantity=0)
    # only ADJUST accepts signed quantities
    with pytest.raises(ValueError, match="positive"):
        _movement(kind="RESERVE", quantity=-4, order_id="order-1")


def test_movement_is_immutable_append_only_record() -> None:
    movement = _movement()

    assert movement.kind == MovementKind.ADJUST
    assert movement.note == "stock inicial"
    assert movement.occurred_at == NOW
    assert movement.movement_id == "movement-1"
