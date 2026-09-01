from __future__ import annotations


def register_models() -> None:
    """Import every ORM model so SQLAlchemy can resolve cross-module foreign keys."""
    from cycling_workshop.bicycles import models as bicycle_models  # noqa: F401
    from cycling_workshop.customers import models as customer_models  # noqa: F401
    from cycling_workshop.events import models as event_models  # noqa: F401
    from cycling_workshop.identity import models as identity_models  # noqa: F401
    from cycling_workshop.jobs import models as job_models  # noqa: F401
    from cycling_workshop.service_orders import models as service_order_models  # noqa: F401
    from cycling_workshop.sync import models as sync_models  # noqa: F401
    from cycling_workshop.tenancy import models as tenancy_models  # noqa: F401
