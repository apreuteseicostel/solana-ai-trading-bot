# Metadata-quality annotations (Issue #6)

The read-only scanner records basic token-creation metadata quality separately from any security or fraud judgment.

Proposed SQLite table: `token_quality_annotations`, keyed by token mint and linked to `token_creations`. Store an immutable first-seen `accepted` flag and a JSON array of reason codes. Replays may backfill a missing flag, but must not overwrite an existing one.

All parsed observations remain stored, including records with poor metadata. Insert the observation and annotation in one transaction. A failure to persist either must roll back both.

`accepted` means that basic metadata-shape checks passed. It does **not** mean the token is safe, that a rug pull is unlikely, or that trading is recommended.

Required tests: replay idempotency, backfill, rollback, and live callback using a stub (no provider connection). No wallet keys, signing, real trades, or changes to main.
