# Evaluation Center

Datasets:

- `data/eval_sets/rag_eval.jsonl`
- `data/eval_sets/agent_eval.jsonl`
- `data/eval_sets/sql_eval.jsonl`

Run:

```bash
python scripts/run_eval.py --target all
```

Outputs:

- `reports/eval_report.json`
- `reports/eval_report.md`

The evaluator uses lightweight deterministic heuristics. It leaves room for RAGAS or LLM-as-judge integration through `packages/evaluation`.
