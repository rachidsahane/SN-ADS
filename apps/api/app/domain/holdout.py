"""Test rows (LLD 5.3): about 20 % of the rows, deterministic, never changes."""

import hashlib


def is_holdout(source: str, external_id: int) -> bool:
    digest = hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 5 == 0
