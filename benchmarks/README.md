# Benchmarks

One file per model version, written by:

```bash
python3 tools/aggregate_evals.py WORKSPACE --model MODEL_ID --json benchmarks/MODEL_ID.json
```

Diff the newest against the previous one with `tools/diff_benchmark.py`. See
[docs/EVALUATING.md](../docs/EVALUATING.md) for what the verdicts mean and what
to do about each.

**These are not scores.** A benchmark is a snapshot of how much difference each
skill made to one model on one date. The only use for an old one is subtraction.
