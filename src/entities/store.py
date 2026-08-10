import json
import sqlite3
from pathlib import Path

from src.entities.models import (
    CannotLinkConstraint,
    ChangeRecord,
    Evidence,
    EvidenceLink,
    Symbol,
)

"""
SQLite-backed repository for the entity/symbol layer.

This is deliberately a relational store, not ChromaDB: change/evidence/link
records are graph-shaped with composite keys and hard constraints, which
ChromaDB's flat vector+metadata model doesn't represent well. ChromaDB stays
the semantic layer used elsewhere in the pipeline (chunk embeddings); this
store is the identity/evidence layer.
"""

DEFAULT_DB_PATH = Path("data/entities.db")


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Open a SQLite connection with row access by column name.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A SQLite connection with row_factory set to sqlite3.Row.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not already exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS change_records (
            change_id TEXT PRIMARY KEY,
            symbol_name TEXT NOT NULL,
            symbol_package TEXT NOT NULL,
            symbol_kind TEXT,
            version_from TEXT,
            version_to TEXT,
            change_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            external_refs TEXT NOT NULL,
            replacement_symbol TEXT,
            parameters TEXT NOT NULL,
            migration_action_text TEXT,
            source_type TEXT NOT NULL,
            source_document_id TEXT NOT NULL,
            raw_text TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_change_records_symbol
            ON change_records (symbol_name, symbol_package);

        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_document_id TEXT NOT NULL,
            symbol_mentions TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            external_refs TEXT NOT NULL,
            embedding_id TEXT
        );

        CREATE TABLE IF NOT EXISTS evidence_links (
            evidence_id TEXT NOT NULL,
            change_id TEXT NOT NULL,
            link_type TEXT NOT NULL,
            link_confidence REAL NOT NULL,
            confidence_tier TEXT NOT NULL,
            link_method TEXT NOT NULL,
            provenance TEXT NOT NULL,
            review_status TEXT NOT NULL,
            PRIMARY KEY (evidence_id, change_id),
            FOREIGN KEY (evidence_id) REFERENCES evidence (evidence_id),
            FOREIGN KEY (change_id) REFERENCES change_records (change_id)
        );

        CREATE TABLE IF NOT EXISTS cannot_link_constraints (
            change_id_a TEXT NOT NULL,
            change_id_b TEXT NOT NULL,
            reason TEXT NOT NULL,
            provenance TEXT NOT NULL,
            created_by TEXT NOT NULL,
            PRIMARY KEY (change_id_a, change_id_b)
        );
        """
    )
    conn.commit()


def _normalize_pair(change_id_a: str, change_id_b: str) -> tuple[str, str]:
    """Cannot-link constraints are symmetric; store them under a fixed order."""
    a, b = sorted((change_id_a, change_id_b))
    return a, b


def _row_to_change_record(row: sqlite3.Row) -> ChangeRecord:
    return ChangeRecord(
        symbol=Symbol(
            name=row["symbol_name"],
            package=row["symbol_package"],
            kind=row["symbol_kind"],
        ),
        version_from=row["version_from"],
        version_to=row["version_to"],
        change_type=row["change_type"],
        summary=row["summary"],
        external_refs=json.loads(row["external_refs"]),
        replacement_symbol=row["replacement_symbol"],
        parameters=json.loads(row["parameters"]),
        migration_action_text=row["migration_action_text"],
        change_id=row["change_id"],
        source_type=row["source_type"],
        source_document_id=row["source_document_id"],
        raw_text=row["raw_text"],
    )


def insert_change_record(conn: sqlite3.Connection, change: ChangeRecord) -> None:
    conn.execute(
        """
        INSERT INTO change_records (
            change_id, symbol_name, symbol_package, symbol_kind,
            version_from, version_to, change_type, summary,
            external_refs, replacement_symbol, parameters, migration_action_text,
            source_type, source_document_id, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            change.change_id,
            change.symbol.name,
            change.symbol.package,
            change.symbol.kind,
            change.version_from,
            change.version_to,
            change.change_type,
            change.summary,
            json.dumps(change.external_refs),
            change.replacement_symbol,
            json.dumps(change.parameters),
            change.migration_action_text,
            change.source_type,
            change.source_document_id,
            change.raw_text,
        ),
    )
    conn.commit()


def get_change_record(conn: sqlite3.Connection, change_id: str) -> ChangeRecord | None:
    row = conn.execute(
        "SELECT * FROM change_records WHERE change_id = ?", (change_id,)
    ).fetchone()
    return _row_to_change_record(row) if row else None


def find_candidates_by_symbol(
    conn: sqlite3.Connection,
    symbol: Symbol,
    version_to: str | None = None,
) -> list[ChangeRecord]:
    """
    Blocking query: narrow candidates to those sharing the same symbol
    identity (name + package). This is a coarse pre-filter only -- it does
    not decide identity, it just bounds what pairwise resolution has to look
    at. When version_to is known, candidates with a known-and-different
    version_to are excluded too (finer version compatibility checks still
    belong to constraints/pairwise, not here).
    """
    rows = conn.execute(
        """
        SELECT * FROM change_records
        WHERE symbol_name = ? AND symbol_package = ?
        """,
        (symbol.name, symbol.package),
    ).fetchall()

    candidates = [_row_to_change_record(row) for row in rows]

    if version_to is not None:
        candidates = [
            c for c in candidates if c.version_to is None or c.version_to == version_to
        ]

    return candidates


def insert_evidence(conn: sqlite3.Connection, evidence: Evidence) -> None:
    conn.execute(
        """
        INSERT INTO evidence (
            evidence_id, source_type, source_document_id,
            symbol_mentions, raw_text, external_refs, embedding_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence.evidence_id,
            evidence.source_type,
            evidence.source_document_id,
            json.dumps(
                [
                    {"name": s.name, "package": s.package, "kind": s.kind}
                    for s in evidence.symbol_mentions
                ]
            ),
            evidence.raw_text,
            json.dumps(evidence.external_refs),
            evidence.embedding_id,
        ),
    )
    conn.commit()


def get_evidence(conn: sqlite3.Connection, evidence_id: str) -> Evidence | None:
    row = conn.execute(
        "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
    ).fetchone()

    if not row:
        return None

    return Evidence(
        evidence_id=row["evidence_id"],
        source_type=row["source_type"],
        source_document_id=row["source_document_id"],
        symbol_mentions=[
            Symbol(name=s["name"], package=s["package"], kind=s["kind"])
            for s in json.loads(row["symbol_mentions"])
        ],
        raw_text=row["raw_text"],
        external_refs=json.loads(row["external_refs"]),
        embedding_id=row["embedding_id"],
    )


def insert_evidence_link(conn: sqlite3.Connection, link: EvidenceLink) -> None:
    conn.execute(
        """
        INSERT INTO evidence_links (
            evidence_id, change_id, link_type, link_confidence,
            confidence_tier, link_method, provenance, review_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            link.evidence_id,
            link.change_id,
            link.link_type,
            link.link_confidence,
            link.confidence_tier,
            link.link_method,
            link.provenance,
            link.review_status,
        ),
    )
    conn.commit()


def _row_to_evidence_link(row: sqlite3.Row) -> EvidenceLink:
    return EvidenceLink(
        evidence_id=row["evidence_id"],
        change_id=row["change_id"],
        link_type=row["link_type"],
        link_confidence=row["link_confidence"],
        confidence_tier=row["confidence_tier"],
        link_method=row["link_method"],
        provenance=row["provenance"],
        review_status=row["review_status"],
    )


def get_links_for_change(conn: sqlite3.Connection, change_id: str) -> list[EvidenceLink]:
    rows = conn.execute(
        "SELECT * FROM evidence_links WHERE change_id = ?", (change_id,)
    ).fetchall()
    return [_row_to_evidence_link(row) for row in rows]


def get_links_for_evidence(conn: sqlite3.Connection, evidence_id: str) -> list[EvidenceLink]:
    rows = conn.execute(
        "SELECT * FROM evidence_links WHERE evidence_id = ?", (evidence_id,)
    ).fetchall()
    return [_row_to_evidence_link(row) for row in rows]


def insert_cannot_link(conn: sqlite3.Connection, constraint: CannotLinkConstraint) -> None:
    change_id_a, change_id_b = _normalize_pair(
        constraint.change_id_a, constraint.change_id_b
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO cannot_link_constraints (
            change_id_a, change_id_b, reason, provenance, created_by
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (change_id_a, change_id_b, constraint.reason, constraint.provenance, constraint.created_by),
    )
    conn.commit()


def get_cannot_link(
    conn: sqlite3.Connection, change_id_a: str, change_id_b: str
) -> CannotLinkConstraint | None:
    change_id_a, change_id_b = _normalize_pair(change_id_a, change_id_b)
    row = conn.execute(
        """
        SELECT * FROM cannot_link_constraints
        WHERE change_id_a = ? AND change_id_b = ?
        """,
        (change_id_a, change_id_b),
    ).fetchone()

    if not row:
        return None

    return CannotLinkConstraint(
        change_id_a=row["change_id_a"],
        change_id_b=row["change_id_b"],
        reason=row["reason"],
        provenance=row["provenance"],
        created_by=row["created_by"],
    )
