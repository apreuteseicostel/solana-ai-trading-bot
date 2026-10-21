# Metadata-quality annotations (Issue #6)

The read-only scanner persists an optional first-seen **metadata-quality** result
next to each token-creation observation in SQLite (`token_quality_annotations`).
An annotation contains `accepted` and a JSON array of deterministic reason codes.
The `accepted` field means **metadata shape passed basic checks**; it is **not**
a fraud verdict, token security audit, investment recommendation, or trade signal.
All parsed observations are stored regardless of their quality flags.

New databases create the annotation table automatically. Existing databases are
upgraded non-destructively by `CREATE TABLE IF NOT EXISTS`. When replaying an
older event, the first annotation may be backfilled without changing the event.
Repeated mints do not overwrite the first stored annotation. Event and annotation
writes are in one SQLite transaction; failures roll back both. Call
`TokenEventStore.get_quality(mint)` to read the annotation, or `None` if absent.

No private keys, wallet access, signing, trading, network requests or changes to
`main` are required. The quality logic cannot identify rug pulls or other
on-chain fraud. Provider connectivity and real-world trading performance remain
unvalidated. This feature is intended only for review in a Draft PR.
