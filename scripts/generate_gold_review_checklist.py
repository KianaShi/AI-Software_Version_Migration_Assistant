import json
import sqlite3
from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import run_pipeline

"""
Generate a human-reviewable checklist (v2) from
data/gold/pydantic_gold_queries.json: resolves each required_change_id /
relevant_evidence_id / stability_evidence_id back into readable
symbol/change_type/migration-action/evidence text instead of opaque
hashes, so a reviewer can judge correctness without cross-referencing the
database by hand.
"""

GOLD_PATH = Path("data/gold/pydantic_gold_queries.json")
OUTPUT_PATH = Path("data/gold/pydantic_gold_review_checklist.md")

FLAGGED_TYPES = {
    "multi_change",
    "underspecified_symbol",
    "behavioral_change",
    "negative",
}


def main() -> None:
    data = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    metadata = data["metadata"]
    gold = data["queries"]
    chunks, conn, _stats = run_pipeline()
    conn.row_factory = sqlite3.Row
    chunks_by_id = {c.chunk_id: c for c in chunks}

    changes = {r["change_id"]: dict(r) for r in conn.execute("SELECT * FROM change_records")}
    evidence = {r["evidence_id"]: dict(r) for r in conn.execute("SELECT * FROM evidence")}

    lines = [
        f"# {metadata['name']} — Human Review Checklist (review_revision={metadata['review_revision']})",
        "",
        f"Scope: {metadata['migration_scope']}. Status: `{metadata['status']}`.",
        "",
        "Generated from `data/gold/pydantic_gold_queries.json` against the live "
        "corpus/entities.db, rebuilt fresh by this script. For each query, review:",
        "",
        "1. Is the query itself reasonable/realistic?",
        "2. Are `required_change_ids` correct and complete?",
        "3. Does the evidence text actually support the query, and does the "
        "recommended migration action (not just the deprecation label) look right?",
        "4. Is `query_type` the right taxonomy bucket?",
        "",
        "⚠️ = flagged taxonomy (multi_change / underspecified_symbol / "
        "behavioral_change / negative) — highest mislabeling risk, review "
        "these first. `legacy_symbol` and `single_change`/`exact_symbol` are "
        "lower risk (Stage 8A already split out the genuinely ambiguous case "
        "as `underspecified_symbol`).",
        "",
        "Note: `multi_change` means multiple changes co-occurring within the "
        "single 1.10.x→2.x transition this benchmark covers -- **not** "
        "version-path multi-hop (v2→v3→v4→v5), which this corpus cannot "
        "test and isn't claimed anywhere in this checklist.",
        "",
        "---",
        "",
    ]

    by_type: dict[str, list[dict]] = {}
    for q in gold:
        by_type.setdefault(q["query_type"], []).append(q)

    for query_type in sorted(by_type):
        flag = " ⚠️" if query_type in FLAGGED_TYPES else ""
        lines.append(f"## {query_type}{flag} ({len(by_type[query_type])} queries)")
        lines.append("")

        for q in by_type[query_type]:
            scope = q.get("evaluation_scope", "retrieval")
            scope_note = "" if scope == "retrieval" else f" — **evaluation_scope={scope}, excluded from core Recall@K aggregate**"
            lines.append(f"### `{q['query_id']}`{scope_note}")
            lines.append(f"**Query**: {q['query_text']}")
            lines.append(
                f"**from/to version**: {q.get('from_version')} → {q.get('to_version')}"
            )
            lines.append("")

            if not q["required_change_ids"]:
                lines.append("**required_change_ids**: _(none — negative query)_")
            else:
                lines.append("**required_change_ids**:")
                for cid in q["required_change_ids"]:
                    c = changes.get(cid)
                    if c is None:
                        lines.append(f"- `{cid}` — ⚠️ NOT FOUND IN DB")
                        continue
                    status_label = c["change_type"]
                    if c["replacement_symbol"]:
                        action = f"**Migration action: use `{c['replacement_symbol']}`**"
                    elif c.get("migration_action_text"):
                        action = f"**Migration action: {c['migration_action_text']}**"
                    else:
                        action = "_(no replacement/action found in evidence -- status-only fact; see deprecated_action_audit.md)_"
                    lines.append(
                        f"- `{cid}` — **{c['symbol_name']}** ({status_label}). {action}. "
                        f"version_to={c['version_to']}"
                    )

            lines.append("")

            if not q["relevant_evidence_ids"]:
                lines.append("**relevant_evidence_ids**: _(none)_")
            else:
                lines.append("**relevant_evidence_ids**:")
                for eid in q["relevant_evidence_ids"]:
                    e = evidence.get(eid)
                    if e is None:
                        lines.append(f"- `{eid}` — ⚠️ NOT FOUND IN DB")
                        continue
                    lines.append(f"- `{eid}` [{e['source_type']}] — {e['raw_text']}")

            stability_ids = q.get("stability_evidence_ids") or []
            if stability_ids:
                lines.append("")
                lines.append("**stability_evidence_ids** (proves nothing changed, not an extracted change):")
                for chunk_id in stability_ids:
                    chunk = chunks_by_id.get(chunk_id)
                    if chunk is None:
                        lines.append(f"- `{chunk_id}` — ⚠️ NOT FOUND IN CORPUS")
                        continue
                    lines.append(f"- `{chunk_id}` [{chunk.source_type}] — {chunk.text}")

            lines.append("")
            lines.append(
                "**Reviewer notes**: _(query reasonable? / change_ids correct? / "
                "migration action correct? / evidence supports it? / taxonomy correct?)_"
            )
            lines.append("")
            lines.append("---")
            lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote review checklist to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
