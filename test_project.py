import sqlite3
import unittest
from project import assess, decide, demo, enqueue, prepare


class ReviewTests(unittest.TestCase):
    def test_missing_evidence_and_uncertainty_surface_as_flags(self):
        result = demo()
        self.assertEqual(result["parsed"]["flagged"], ["total_cents", "currency"])
        self.assertTrue(result["stale_edit_rejected"])
        self.assertEqual(result["audit_entries"], 1)

    def test_tenant_correct_quantity_type_and_valid_confidence(self):
        with sqlite3.connect(":memory:") as db:
            prepare(db)
            enqueue(db, "north", 1, {})
            self.assertIsNone(decide(db, "harbor", 1, 1, "Reviewer B", "accepted"))
        review = assess({"total_cents": {"value": True, "confidence": 2, "line": "??"}})
        self.assertIsNone(review["fields"]["total_cents"])
