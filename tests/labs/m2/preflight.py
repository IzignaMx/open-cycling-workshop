"""Read-only M2 blocker inventory; this module cannot authorize execution.

Command presence is diagnostic only. No runtime enforcement receipt producer or
verifier exists in this increment, so even a fully equipped host remains blocked.
No subprocesses, network, credentials, environment DSNs or production imports.
"""

import json
import platform
import shutil
import time
from dataclasses import dataclass

REQUIRED_RUNTIME_EVIDENCE = (
    "postgresql18-transaction-evidence-missing",
    "verified-tls-endpoint-evidence-missing",
    "separate-nonroot-process-evidence-missing",
    "enforced-egress-and-mount-policy-evidence-missing",
    "enforced-resource-and-transport-limits-evidence-missing",
    "run-deadline-and-clock-integrity-evidence-missing",
    "synthetic-owned-database-evidence-missing",
    "verified-teardown-receipt-missing",
)


@dataclass(frozen=True)
class EnvironmentFacts:
    """Presence observations only, never security attestations."""

    docker_available: bool
    psql_available: bool
    suspend_inclusive_clock_available: bool


@dataclass(frozen=True)
class AdmissionReport:
    unmet: tuple[str, ...]

    @property
    def execution_authorized(self) -> bool:
        # Deliberately no allow branch until enforced runtime evidence is designed.
        return False


def assess(facts: EnvironmentFacts) -> AdmissionReport:
    unmet = list(REQUIRED_RUNTIME_EVIDENCE)
    if not facts.docker_available:
        unmet.append("docker-unavailable")
    if not facts.psql_available:
        unmet.append("psql-unavailable")
    if not facts.suspend_inclusive_clock_available:
        unmet.append("suspend-inclusive-clock-unavailable")
    return AdmissionReport(tuple(unmet))


def probe() -> EnvironmentFacts:
    """Observe local capabilities without invoking tools or reading configuration."""
    return EnvironmentFacts(
        docker_available=shutil.which("docker") is not None,
        psql_available=shutil.which("psql") is not None,
        suspend_inclusive_clock_available=(
            platform.system() == "Linux" and hasattr(time, "CLOCK_BOOTTIME")
        ),
    )


def main() -> int:
    report = assess(probe())
    print(
        json.dumps(
            {
                "status": "blocked",
                "execution_authorized": report.execution_authorized,
                "unmet": report.unmet,
            },
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
