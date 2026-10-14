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
  --env PGPASSWORD --env PGCONNECTTIMEOUT --env PGAPPNAME \
  postgres:18.4-trixie "$tool" "$@"
CLIENT
  chmod 0700 "$client_dir/$tool"
done
export PATH="$client_dir:$PATH"
# Fail before pytest rather than letting its developer-friendly skip look green.
pg_dump --version | grep -E '\(PostgreSQL\) 18\.'
pg_restore --version | grep -E '\(PostgreSQL\) 18\.'
test -n "${OCWP_TEST_DATABASE_URL:-}"
export BRANDING_RECOVERY_STARTED_NS="$(date +%s%N)"
uv run pytest -q tests/operations/test_branding_recovery_postgres.py \
  --basetemp=artifacts/branding-recovery
uv run python - <<'PY'
import json
import os
from pathlib import Path

files = list(Path("artifacts/branding-recovery").rglob("branding-recovery-evidence.json"))
if len(files) != 1:
    raise SystemExit("Branding recovery did not produce its required single proof artifact")
if files[0].stat().st_mtime_ns < int(os.environ["BRANDING_RECOVERY_STARTED_NS"]):
    raise SystemExit("Branding recovery evidence is stale; this run is not qualified")
proof = json.loads(files[0].read_text())
assert proof["authenticated_profile_smoke_tested"] is True
assert proof["stale_sessions_and_checkpoint_refused"] is True
assert len(proof["profiles"]) == 3
assert all(row["expected_sha256"] == row["actual_sha256"] for row in proof["profiles"])
print("Confirmed authenticated three-profile recovery proof; no dump or logo bytes are uploaded.")
PY
