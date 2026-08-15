import secrets


def generate_public_id(prefix: str) -> str:
    """Generate a compact, URL-safe opaque identifier for public permalinks."""
    return f'{prefix}_{secrets.token_urlsafe(9)}'
