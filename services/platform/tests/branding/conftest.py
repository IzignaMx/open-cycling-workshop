import sys
from pathlib import Path

# Reuse the established synthetic multi-tenant HTTP fixture.
IDENTITY_TESTS = str(Path(__file__).resolve().parents[1] / "identity")
if IDENTITY_TESTS not in sys.path:
    sys.path.insert(0, IDENTITY_TESTS)
