from __future__ import annotations

import json
import unittest

from data.process.chunking import chunk_document
from data.process.loader import SOURCE_FILES, load_documents
from data.pipelines.generation import unsupported_numeric_claim


class CorpusPipelineTests(unittest.TestCase):
    def test_allowlisted_manuals_load_and_each_has_three_chunks(self) -> None:
        documents = load_documents()
        self.assertEqual({doc.source_document for doc in documents}, set(SOURCE_FILES))
        for document in documents:
            with self.subTest(source=document.source_document):
                chunks = chunk_document(document)
                self.assertGreaterEqual(len(chunks), 3)
                self.assertTrue(all(chunk.text.strip() for chunk in chunks))
                self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))
                self.assertTrue(all(c.source_document == document.source_document for c in chunks))

    def test_eval_has_sixteen_in_scope_and_two_out_of_scope(self) -> None:
        from pathlib import Path

        eval_file = Path(__file__).resolve().parents[1] / "eval" / "test-queries.json"
        cases = json.loads(eval_file.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 18)
        self.assertEqual(sum(case["expected_source_document"] is not None for case in cases), 16)
        self.assertEqual(sum(case["expected_source_document"] is None for case in cases), 2)

    def test_numeric_guard_only_allows_numbers_found_in_evidence(self) -> None:
        context = "El pedido se realiza el lunes antes de las 11:00."
        self.assertFalse(unsupported_numeric_claim("El pedido se realiza el lunes a las 11:00.", context))
        self.assertTrue(unsupported_numeric_claim("El pedido se realiza el lunes a las 10:00.", context))


if __name__ == "__main__":
    unittest.main()
