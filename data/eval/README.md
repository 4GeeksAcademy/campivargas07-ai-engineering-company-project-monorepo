# `data/eval` folder

This folder is for **evaluation and validation**: evaluation datasets, golden sets, experiment results, metrics, and artifacts used to measure quality for models, RAG, agents, or pipelines.

- **Main purpose**: centralize evaluation inputs and outputs so improvements stay measurable across project milestones.
- **Recommendation**: document each evaluation set (what it measures, how it was built, success criteria) and avoid sensitive data; use synthetic or anonymized data when needed.

## Brasaland RAG evaluation

`test-queries.json` retains the 16 original in-scope questions and two out-of-scope questions. Every `expected_evidence` excerpt is checked against its pinned manual before requests. A hit requires **all** expected excerpts, intact, within the first three chunks from the expected source. Compound questions may require multiple chunks. Only case and whitespace are normalized; amounts, units, currencies and conditions remain literal. Matching a document or section label alone is insufficient. Retrieval errors remain misses in the fixed denominator of 16; the target requires 13 hits.

From the repository root, with API dependencies installed and approved configuration exported locally:

```bash
services/api/.venv/bin/python -m data.eval.run_evaluation --retrieval-only --output /tmp/brasaland-retrieval-01.json
services/api/.venv/bin/python -m data.eval.run_evaluation --output /tmp/brasaland-rag-01.json
```

The full run uses the same top-5 and context builder as `query`, scores Recall on the first three, and saves the exact context and generated answer. Out-of-scope answers and a separate malicious-context experiment are retained for human review and excluded from Recall. Artifacts contain UTC timestamps, non-secret configuration, model IDs, corpus/code/dataset hashes, chunk counts, versions and stage failures. Keys, endpoint URLs and exception messages are omitted. Missing configuration produces a blocked report with null metrics and no calls; existing output files are never overwritten. CLI exit code 1 means blocked, execution errors or a missed Recall target.

Faithfulness is a separate manual assessment: review claims/citations, numbers, COP/USD, conditions, allergens, insufficiency and injection resistance against each saved context. Fill `manual_review` with findings and reviewer. `attack_marker_present` is a diagnostic, not a complete fidelity check; `faithfulness.measured_score` remains null until documented review. Generation failures never become successful replacement answers. Compare separate retrieval runs to justify the threshold; vector scores are not probabilities. Injected offline fixtures are explicitly labeled and cannot establish a real KPI.

Offline contract checks:

```bash
python3 -m unittest data.tests.test_evaluation -v
```

> _Spanish version: [README.es.md](./README.es.md)._
