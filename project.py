"""Route uncertain synthetic document fields to a versioned human review queue."""

import argparse
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path

FIELDS = ("reference", "total_cents", "currency")


def assess(extraction):
    fields = {}
    reasons = []
    for key in FIELDS:
        item = extraction.get(key, {})
        confidence = item.get("confidence", 0)
        value = item.get("value")
        valid_value = (
            (type(value) is int and value >= 0)
            if key == "total_cents"
            else isinstance(value, str) and bool(value.strip())
        )
        if key == "currency":
            valid_value = value in ("USD", "EUR", "GBP")
        valid_confidence = (
            type(confidence) in (int, float)
            and math.isfinite(confidence)
            and 0.9 <= confidence <= 1
        )
        if not valid_value or not valid_confidence or not item.get("line"):
            reasons.append(key)
        fields[key] = value if valid_value else None
    return {"fields": fields, "flagged": reasons, "recommended": "review" if reasons else "ready"}


def prepare(db):
    db.executescript("""CREATE TABLE IF NOT EXISTS docs (tenant TEXT, id INTEGER, review TEXT, state TEXT, version INTEGER,
      PRIMARY KEY(tenant,id)); CREATE TABLE IF NOT EXISTS audit (tenant TEXT, id INTEGER, version INTEGER, actor TEXT, decision TEXT,
      PRIMARY KEY(tenant,id,version));""")


def enqueue(db, tenant, document_id, extraction):
    preview = assess(extraction)
    with db:
        db.execute(
            "INSERT INTO docs VALUES (?,?,?,'queued',1)", (tenant, document_id, json.dumps(preview))
        )
    return preview


def decide(db, tenant, document_id, version, actor, decision):
    if decision not in ("accepted", "rejected") or not actor:
        raise ValueError("Decision requires a named reviewer")
    with db:
        changed = db.execute(
            "UPDATE docs SET state=?,version=version+1 WHERE tenant=? AND id=? AND state='queued' AND version=?",
            (decision, tenant, document_id, version),
        ).rowcount
        if not changed:
            return None
        db.execute(
            "INSERT INTO audit VALUES (?,?,?,?,?)",
            (tenant, document_id, version + 1, actor, decision),
        )
        return {"document_id": document_id, "decision": decision, "version": version + 1}


def demo():
    input_fields = {
        "reference": {"value": "S-521", "confidence": 0.98, "line": "Ref S-521"},
        "total_cents": {"value": 12305, "confidence": 0.64, "line": "Total 123.05"},
    }
    with closing(sqlite3.connect(":memory:")) as db:
        prepare(db)
        preview = enqueue(db, "workshop", 1, input_fields)
        rejected = decide(db, "workshop", 1, 1, "Reviewer A", "rejected")
        stale = decide(db, "workshop", 1, 1, "Reviewer B", "accepted")
        return {
            "parsed": preview,
            "recorded": rejected,
            "stale_edit_rejected": stale is None,
            "audit_entries": db.execute("SELECT count(*) FROM audit").fetchone()[0],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["demo", "enqueue", "queue", "decide"], default="demo", nargs="?"
    )
    parser.add_argument("--database", type=Path, default=Path("review.sqlite"))
    parser.add_argument("--tenant", default="workshop")
    parser.add_argument("--document", type=int)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--version", type=int)
    parser.add_argument("--reviewer")
    parser.add_argument("--decision", choices=["accepted", "rejected"])
    args = parser.parse_args()
    if args.command == "demo":
        result = demo()
    else:
        with closing(sqlite3.connect(args.database)) as db:
            prepare(db)
            if args.command == "enqueue" and args.document is not None and args.input:
                result = enqueue(
                    db,
                    args.tenant,
                    args.document,
                    json.loads(args.input.read_text(encoding="utf-8")),
                )
            elif args.command == "queue":
                result = [
                    {"id": item, "extraction": json.loads(reviews), "version": version}
                    for item, reviews, version in db.execute(
                        "SELECT id,review,version FROM docs WHERE tenant=? AND state='queued' ORDER BY id",
                        (args.tenant,),
                    )
                ]
            elif args.command == "decide" and all(
                (args.document, args.version, args.reviewer, args.decision)
            ):
                result = decide(
                    db, args.tenant, args.document, args.version, args.reviewer, args.decision
                )
                if result is None:
                    parser.exit(
                        2,
                        "The item changed or is unavailable for this tenant. Refresh the queue.\n",
                    )
            else:
                parser.error(
                    "Enqueue needs --document and --input. Decide needs --document, --version, --reviewer, and --decision."
                )
    print(json.dumps(result, indent=2))
