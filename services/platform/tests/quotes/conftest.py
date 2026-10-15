import sys
from pathlib import Path

# Reuse safe, isolated SQLite/PostgreSQL migration fixture routing.
IDENTITY_TESTS = str(Path(__file__).resolve().parents[1] / "identity")
if IDENTITY_TESTS not in sys.path:
    sys.path.insert(0, IDENTITY_TESTS)

# Reuse the established UUID-database restore fixture and its libpq/client guards.
OPERATIONS_TESTS = str(Path(__file__).resolve().parents[4] / "tests" / "operations")
if OPERATIONS_TESTS not in sys.path:
    sys.path.insert(0, OPERATIONS_TESTS)
