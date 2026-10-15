from __future__ import annotations

from collections import Counter
from contextlib import chdir
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from data.eval.run_evaluation import load_cases, normalize_evidence, run, score_retrieval
from data.process.chunking import chunk_documents
from data.process.loader import load_documents


def matching_chunks(case: dict) -> list[dict]:
    if case["expected_source_document"] is None:
        return []
    return [{"id": case["id"], "source_document": case["expected_source_document"],
             "section": case["expected_section"], "score": 0.9,
             "text": "\n".join(case["expected_evidence"])}]


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_cases()
        self.by_question = {case["question"]: case for case in self.cases}

    def test_dataset_keeps_original_ids_and_evidence_occurs_in_source_chunks(self) -> None:
        expected_ids = {f"{source}-{number:02}" for source in ("loyalty", "waste", "allergens", "suppliers")
                        for number in range(1, 5)} | {"out-of-scope-01", "out-of-scope-02"}
        self.assertEqual({case["id"] for case in self.cases}, expected_ids)
        counts = Counter(case["expected_source_document"] for case in self.cases)
        self.assertEqual(counts[None], 2)
        chunks = chunk_documents(load_documents())
        for case in self.cases:
            if case["expected_source_document"] is None:
                continue
            with self.subTest(case=case["id"]):
                relevant = [
                    {"source_document": chunk.source_document, "text": chunk.text}
                    for chunk in chunks if chunk.source_document == case["expected_source_document"]
                    and any(normalize_evidence(excerpt) in normalize_evidence(chunk.text)
                            for excerpt in case["expected_evidence"])
                ]
                # Every original question is answerable without needing more
                # than three semantic chunks; retrieval still has to find them.
                self.assertLessEqual(len(relevant), 3)
                self.assertTrue(score_retrieval(case, relevant)["hit"])

    def test_titles_metadata_or_unrelated_numbers_never_count_as_evidence(self) -> None:
        case = self.cases[2]  # Oro
        chunk = matching_chunks(case)[0]
        chunk["text"] = 'Programa de Lealtad "Brasa Points"\n50+ puntos de otra promoción.'
        self.assertFalse(score_retrieval(case, [chunk])["hit"])
        chunk["text"] = "\n".join(case["expected_evidence"])
        chunk["source_document"] = "waste-protocol"
        self.assertFalse(score_retrieval(case, [chunk])["hit"])

    def test_compound_question_requires_all_facts_in_first_three_intact_chunks(self) -> None:
        case = next(case for case in self.cases if case["id"] == "suppliers-04")
        first = {"source_document": case["expected_source_document"], "text": case["expected_evidence"][0]}
        second = {"source_document": case["expected_source_document"], "text": case["expected_evidence"][1]}
        self.assertFalse(score_retrieval(case, [first])["hit"])
        self.assertTrue(score_retrieval(case, [first, second])["hit"])
        distractor = {"source_document": case["expected_source_document"], "text": "Otro párrafo"}
        self.assertFalse(score_retrieval(case, [first, distractor, distractor, second])["hit"])
        second["text"] = second["text"].replace("si supera 500 USD", "si no supera 500 USD")
        self.assertFalse(score_retrieval(case, [first, second])["hit"])

    def test_evidence_normalizes_line_wraps_but_preserves_numbers_units_and_conditions(self) -> None:
        case = self.cases[0]
        chunk = matching_chunks(case)[0]
        chunk["text"] = chunk["text"].upper().replace(" ", "\n  ")
        self.assertTrue(score_retrieval(case, [chunk])["hit"])
        chunk["text"] = chunk["text"].replace("10.000", "10,000")
        self.assertFalse(score_retrieval(case, [chunk])["hit"])

    def test_offline_runner_counts_13_of_16_and_retains_out_of_scope_for_generation(self) -> None:
        missed = {"loyalty-01", "waste-01", "allergens-01"}
        retrieval_calls = []
        generation_calls = []

        def get_matches(question: str, *, k: int) -> list[dict]:
            retrieval_calls.append((question, k))
            case = self.by_question[question]
            return [] if case["id"] in missed else matching_chunks(case)

        def get_answer(question: str, context: str) -> str:
            generation_calls.append((question, context))
            return "Respuesta simulada; requiere revisión manual."

        with patch("httpx.Client.request", side_effect=AssertionError("External HTTP forbidden in tests")):
            report = run(retrieval_fn=get_matches, generation_fn=get_answer)
        self.assertEqual(report["evaluation_type"], "offline_fixture")
        self.assertEqual(report["hits"], 13)
        self.assertEqual(report["recall_at_3"], 13 / 16)
        self.assertTrue(report["meets_target"])
        self.assertEqual(len(report["results"]), 18)
        self.assertEqual(len(retrieval_calls), 18)
        self.assertEqual(len(generation_calls), 19)  # 18 originals + separate injection experiment
        self.assertTrue(all(k == 5 for _, k in retrieval_calls))
        self.assertEqual(report["faithfulness"]["status"], "pending_manual_review")
        self.assertIsNone(report["faithfulness"]["measured_score"])
        self.assertIsNone(report["results"][-1]["hit"])
        self.assertEqual(report["results"][-1]["generation_context"], "")
        self.assertEqual(len(report["manifest"]["corpus"]), 4)
        self.assertTrue(all(len(doc["sha256"]) == 64 for doc in report["manifest"]["corpus"]))
        self.assertIn("data/eval/test-queries.json", report["manifest"]["code_and_dataset_sha256"])
        self.assertEqual(len(report["adversarial_probes"]), 1)
        self.assertIn("50+ puntos", report["adversarial_probes"][0]["generation_context"])
        self.assertIn("999 puntos", report["adversarial_probes"][0]["generation_context"])
        self.assertEqual(report["adversarial_probes"][0]["manual_review"]["status"], "pending")

    def test_failures_count_as_misses_keep_denominator_and_never_become_generated_answers(self) -> None:
        def get_matches(question: str, *, k: int) -> list[dict]:
            case = self.by_question[question]
            if case["id"] == "loyalty-01":
                raise TimeoutError("secret-key-in-provider-error")
            return matching_chunks(case)

        def get_answer(question: str, context: str) -> str:
            if question == self.cases[1]["question"]:
                raise RuntimeError("secret-key-in-provider-error")
            return "Respuesta fixture"

        with patch.dict(os.environ, {"GENERATION_API_KEY": "secret-env-key", "QDRANT_URL": "https://user:secret-url@example.test?token=private"}):
            report = run(retrieval_fn=get_matches, generation_fn=get_answer)
        self.assertEqual(report["in_scope_queries"], 16)
        self.assertEqual(report["recall_at_3"], 15 / 16)
        self.assertEqual(report["status"], "completed_with_errors")
        self.assertEqual(report["results"][0]["generation_status"], "not_run_retrieval_error")
        self.assertEqual(report["results"][1]["generation_status"], "error")
        self.assertIsNone(report["results"][1]["answer"])
        self.assertEqual(len(report["failures"]), 2)
        serialized = json.dumps(report)
        for private in ("secret-key-in-provider-error", "secret-env-key", "secret-url", "token=private"):
            self.assertNotIn(private, serialized)

    def test_real_run_without_configuration_never_calls_any_endpoint_or_reports_kpi(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data.eval.run_evaluation.retrieve", side_effect=AssertionError("No endpoint allowed")) as retrieval,
            patch("data.eval.run_evaluation.generate_answer", side_effect=AssertionError("No endpoint allowed")) as generation,
        ):
            report = run()
        retrieval.assert_not_called()
        generation.assert_not_called()
        self.assertEqual(report["status"], "blocked_configuration")
        self.assertIsNone(report["recall_at_3"])
        self.assertIsNone(report["meets_target"])
        self.assertEqual(report["results"], [])

    def test_partial_injection_cannot_accidentally_call_a_real_generator(self) -> None:
        with self.assertRaises(ValueError):
            run(retrieval_fn=lambda question, **kwargs: [])
        report = run(retrieval_fn=lambda question, **kwargs: [], retrieval_only=True)
        self.assertEqual(report["recall_at_3"], 0)
        self.assertFalse(report["meets_target"])
        self.assertEqual(report["faithfulness"]["status"], "not_run")
        self.assertEqual(report["adversarial_probes"], [])

    def test_injection_probe_flags_attack_echo_separately_from_recall(self) -> None:
        def get_matches(question: str, *, k: int) -> list[dict]:
            return matching_chunks(self.by_question[question])

        def get_answer(question: str, context: str) -> str:
            return "ATAQUE_EJECUTADO; 999 puntos" if "INSTRUCCIÓN MALICIOSA" in context else "Fixture"

        report = run(retrieval_fn=get_matches, generation_fn=get_answer)
        self.assertEqual(report["hits"], 16)
        self.assertEqual(report["recall_at_3"], 1)
        self.assertTrue(report["adversarial_probes"][0]["attack_marker_present"])
        self.assertIsNone(report["faithfulness"]["measured_score"])

    def test_missing_evidence_or_removed_cases_invalidates_dataset_before_requests(self) -> None:
        for mutate in (lambda cases: cases.pop(), lambda cases: cases[0].update(expected_evidence=["invented policy"])):
            cases = copy.deepcopy(self.cases)
            mutate(cases)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "queries.json"
                path.write_text(json.dumps(cases), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_cases(path)

    def test_manifest_paths_are_stable_when_runner_is_called_from_api_directory(self) -> None:
        api_directory = Path(__file__).resolve().parents[2] / "services/api"
        with chdir(api_directory):
            report = run(retrieval_fn=lambda question, **kwargs: [], retrieval_only=True)
        hashes = report["manifest"]["code_and_dataset_sha256"]
        self.assertIn("data/eval/test-queries.json", hashes)
        self.assertIn("data/eval/run_evaluation.py", hashes)
        self.assertFalse(any(".." in path for path in hashes))


if __name__ == "__main__":
    unittest.main()
