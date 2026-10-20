# Roadmap

- [x] Simulation-only trading arithmetic
- [x] Unit tests and GitHub Actions CI
- [ ] Audit Chainstack upstream code and license before reuse
- [ ] Add read-only Pump.fun event ingestion
- [ ] Persist market observations and wallet histories
- [x] Market Intelligence V1 implementation: read-only Helius adapter, Jupiter quote-only
  adapter, durable wallet journal, conservative paper-copy engine and dashboard snapshots
- [x] Deterministic offline tests for Market Intelligence V1
- [ ] Credentialed, bounded read-only Helius/Jupiter smoke test
- [ ] Forward paper evaluation, provider billing reconciliation and pool/token security checks
- [ ] Risk scoring, wallet copyability and realistic forward testing
- [ ] Separate explicit approval and security review before live trading

Never commit private keys or seed phrases. No live order execution is implemented.
