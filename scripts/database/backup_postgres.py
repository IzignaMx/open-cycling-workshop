from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.engine import make_url

Runner = Callable[[list[str]], None]


def _libpq_env(database_url: str) -> dict[str, str]:
    url = make_url(database_url)
    if not url.drivername.startswith('postgresql'):
        raise ValueError('PostgreSQL database URL required')
    if not url.database:
        raise ValueError('database name is required')
    env = dict(os.environ)
    env['PGHOST'] = url.host or 'localhost'
    env['PGPORT'] = str(url.port or 5432)
    if url.username:
        env['PGUSER'] = url.username
    if url.password:
        env['PGPASSWORD'] = url.password
    env['PGDATABASE'] = url.database
    return env


def _run(command: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(command, env=env, check=True)


def backup_postgres(
    database_url: str,
    output: Path,
    *,
    runner: Callable[[list[str]], None] | Callable[..., None] = _run,
) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    env = _libpq_env(database_url)
    runner(['pg_dump', '--format=custom', '--file', str(output)], env=env)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError('pg_dump did not produce a non-empty backup')
    return output


def verify_postgres_backup(
    dump: Path,
    *,
    runner: Callable[[list[str]], None] | Callable[..., None] = _run,
) -> None:
    dump = dump.resolve()
    if not dump.is_file() or dump.stat().st_size == 0:
        raise ValueError('backup file is missing or empty')
    runner(['pg_restore', '--list', str(dump)], env=dict(os.environ))
