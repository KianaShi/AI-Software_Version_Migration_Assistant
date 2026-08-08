import sqlite3

from src.entities import store
from src.entities.models import ChangeRecord, Symbol

"""
Level 2 candidate generation (blocking).

Purely structural: symbol name + package identity, with an optional
version_to pre-filter. No embedding similarity is used to select
candidates here -- symbol is a blocking key that narrows the search space,
not an identity key that decides a match. That decision belongs to
pairwise.py.
"""


def generate_candidates(
    conn: sqlite3.Connection,
    symbol: Symbol,
    version_to: str | None = None,
) -> list[ChangeRecord]:
    return store.find_candidates_by_symbol(conn, symbol, version_to=version_to)
