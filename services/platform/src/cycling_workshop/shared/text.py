"""Text admitted to PostgreSQL/UTF-8 storage, without normalization or coercion."""


def validate_storage_text(value: str) -> str:
    """Reject unpersistable code points without echoing private input."""
    if any(character == "\x00" or 0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("text contains unsupported characters")
    return value
