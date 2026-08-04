# Capture parser evaluation dataset

`capture-parser-v1.jsonl` is the versioned fictional acceptance set for both the
deterministic parser and hosted Qwen capture interpretation. Every case uses the
allow-listed entities in `capture-context-v1.json` and a fixed date/timezone so
relative-date expectations are reproducible.

The dataset includes successful drafts, required clarifications and hard rejects.
Model evaluation must compare structured fields rather than prose. A model does
not pass by merely mentioning the right amount; kind, integer paise, account IDs,
date, category and split behavior must match the expected subset.

Run structural validation with:

```bash
python scripts/check_capture_evals.py
```

The Vitest suite imports this same dataset and gates the common and
safety-critical behavior required from the no-provider browser fallback. The
hosted runner will score all 50 records before Qwen is enabled in production.

No real names, account numbers, emails, merchants tied to the user, tokens or
financial values are allowed in this directory.
