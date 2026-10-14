#!/usr/bin/env bash
# Real PG18 filesystem/SQL restore qualification. Only generated evidence JSON
# is publishable; the surrounding basetemp contains restricted synthetic dumps.
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$(pwd -P)"
client_dir="$(mktemp -d)"
trap 'rm -rf "$client_dir"' EXIT
export BRANDING_RECOVERY_WORKSPACE="$root"

docker pull postgres:18.4-trixie
for tool in pg_dump pg_restore; do
  cat > "$client_dir/$tool" <<'CLIENT'
#!/usr/bin/env bash
set -euo pipefail
tool="$(basename "$0")"
case "$tool" in pg_dump|pg_restore) ;; *) exit 64 ;; esac
# No credential values occur in argv. PostgreSQL libpq receives the backup
# boundary's sanitized, explicit PG* environment through Docker by variable name.
exec docker run --rm --network host \
  --user "$(id -u):$(id -g)" --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --volume "$BRANDING_RECOVERY_WORKSPACE:$BRANDING_RECOVERY_WORKSPACE" \
  --workdir "$BRANDING_RECOVERY_WORKSPACE" \
  --env PGHOST --env PGPORT --env PGUSER --env PGDATABASE \
  --env PGPASSWORD --env PGCONNECT_TIMEOUT --env PGAPPNAME \
  postgres:18.4-trixie "$tool" "$@"
CLIENT
  chmod 0700 "$client_dir/$tool"
done
export PATH="$client_dir:$PATH"
# Fail before pytest rather than letting its developer-friendly skip look green.
pg_dump --version | grep -E '\(PostgreSQL\) 18\.'
pg_restore --version | grep -E '\(PostgreSQL\) 18\.'
test -n "${OCWP_TEST_DATABASE_URL:-}"
# pytest creates its explicit basetemp, but not a missing parent. Preserve
# existing permissions and reject untrusted paths before basetemp cleanup.
uv run python - <<'PREPARE'
from pathlib import Path

from scripts.database.branding_bundle import _directory

with _directory(Path.cwd()):
    parent = Path("artifacts")
    parent.mkdir(mode=0o700, exist_ok=True)
    with _directory(parent):
        base = parent / "branding-recovery"
        if base.exists() or base.is_symlink():
            with _directory(base):
                pass
PREPARE
export BRANDING_RECOVERY_STARTED_NS="$(date +%s%N)"
uv run pytest -q tests/operations/test_branding_recovery_postgres.py \
  --basetemp=artifacts/branding-recovery
uv run python - <<'PY'
import json
import os
from pathlib import Path

files = list(Path("artifacts/branding-recovery").rglob("branding-recovery-evidence.json"))
expected = {
    "branding_restore_checked": (0, 2),
    "branding_restore_checked_with_explicit_legacy_cutover": (2, 3),
}
if len(files) != len(expected):
    raise SystemExit("Branding recovery requires both floor-1 and mixed-floor proof artifacts")
observed = set()
for path in files:
    if path.stat().st_mtime_ns < int(os.environ["BRANDING_RECOVERY_STARTED_NS"]):
        raise SystemExit("Branding recovery evidence is stale; this run is not qualified")
    proof = json.loads(path.read_text())
    status = proof["status"]
    assert status in expected and status not in observed
    observed.add(status)
    activated, rotated = expected[status]
    assert type(proof["legacy_organizations_activated"]) is int
    assert type(proof["incarnations_rotated"]) is int
    assert proof["legacy_organizations_activated"] == activated
    assert proof["incarnations_rotated"] == rotated
    assert proof["authenticated_profile_smoke_tested"] is True
    assert proof["stale_sessions_and_checkpoint_refused"] is True
    assert len(proof["profiles"]) == 3
    assert all(row["expected_sha256"] == row["actual_sha256"] for row in proof["profiles"])
assert observed == set(expected)
print("Confirmed floor-1 and mixed-floor authenticated recovery proofs; only safe JSON is uploaded.")
PY
