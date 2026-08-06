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
make eval-capture-validate
```

`make eval-capture-validate` performs a dry validation, writes machine-readable
JSON and human-readable Markdown metadata under `evals/reports/`, requires no
key, and never calls a model.

After configuring the server-only provider environment, run the full benchmark:

```bash
ARTHA_LLM_PROVIDER=groq make eval-capture-hosted
```

`ARTHA_GROQ_API_KEY` must be supplied through the shell or deployment secret
store and must never be pasted into documentation, committed, or passed as a
command-line argument. The runner calls the same `LocalFinancialAssistant`
capture adapter used by the API, runs sequentially with one-second pacing, and
retries one unavailable/invalid response. Rate limits honor the provider's
`Retry-After` header (with a bounded wait), and every completed case is written
atomically to a sanitized checkpoint. If a run is interrupted or quota-limited,
resume it without re-calling already evaluated cases:

```bash
cd apps/api
uv run python -m artha_api.capture_evals --mode run --resume
```

Options can be inspected with:

```bash
cd apps/api
uv run python -m artha_api.capture_evals --help
```

The generated JSON contains overall, outcome, field and tag slices plus only the
constrained structured values for failed cases. Provider failures are classified
separately (for example, `rate_limited` or `timeout`) and excluded from model
accuracy; evaluation coverage remains a separate 100% gate. Reports and
checkpoints deliberately omit utterances, provider response bodies and
model-generated free text. The command exits non-zero when either the strict case
pass rate or coverage gate is missed.

The Vitest suite imports this same dataset and gates the common and
safety-critical behavior required from the no-provider browser fallback. The
hosted runner scores all 50 records before Qwen is enabled in production.

No real names, account numbers, emails, merchants tied to the user, tokens or
financial values are allowed in this directory.
