# Capture model reports

The evaluation runner writes timestamped JSON and Markdown reports here. Generated
reports are ignored by Git until a sanitized result is deliberately reviewed and
published as a documentation artifact.

Never commit a raw provider response. The runner persists only constrained fields
such as outcome, integer paise, allow-listed IDs, split flags and dates; it omits
utterances and all model-generated free text.
