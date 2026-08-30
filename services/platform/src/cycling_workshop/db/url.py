from __future__ import annotations


def normalize_database_url(database_url: str) -> str:
    for prefix in ('postgresql://', 'postgres://'):
        if database_url.startswith(prefix):
            return 'postgresql+psycopg://' + database_url[len(prefix):]
    return database_url
