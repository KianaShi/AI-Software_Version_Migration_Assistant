import json
import sqlite3
from pathlib import Path

"""
Generate a human-reviewable checklist from data/gold/pydantic_gold_queries.json:
resolves each required_change_id / relevant_evidence_id back into readable
symbol/change_type/text instead of opaque hashes, so a reviewer can judge
correctness without cross-referencing the database by hand.
"""

GOLD_PATH = Path("data/gold/pydantic_gold_queries.json")
DB_PATH = Path("data/entities.db")
OUTPUT_PATH = Path("data/gold/pydantic_gold_review_checklist.md")

FLAGGED_TYPES = {"multi_hop", "ambiguous_alias", "behavioral_change", "negative"}


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    changes = {r["change_id"]: dict(r) for r in conn.execute("SELECT * FROM change_records")}
    evidence = {r["evidence_id"]: dict(r) for r in conn.execute("SELECT * FROM evidence")}

    lines = [
        "# Pydantic Gold Set — Human Review Checklist",
        "",
        "Generated from `data/gold/pydantic_gold_queries.json` against the live "
        "`data/entities.db` (commit `8e540dc`). For each query, review:",
        "",
        "1. Is the query itself reasonable/realistic?",
        "2. Are `required_change_ids` correct and complete?",
        "3. Does the evidence text actually support the query?",
        "4. Is `query_type` the right taxonomy bucket?",
        "",
        f"⚠️ = flagged taxonomy (multi_hop / ambiguous_alias / behavioral_change / "
        f"negative) — highest mislabeling risk, review these first.",
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
            lines.append(f"### `{q['query_id']}`")
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
                    repl = f" → `{c['replacement_symbol']}`" if c["replacement_symbol"] else ""
                    lines.append(
                        f"- `{cid}` — **{c['symbol_name']}** ({c['change_type']}){repl}, "
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

            lines.append("")
            lines.append("**Reviewer notes**: _(query reasonable? / change_ids correct? / evidence supports it? / taxonomy correct?)_")
            lines.append("")
            lines.append("---")
            lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote review checklist to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
