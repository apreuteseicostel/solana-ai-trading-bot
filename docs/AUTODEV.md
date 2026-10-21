# AutoDev operating model

The agent workflow has three layers:

1. **Repository automation (implemented):** GitHub Actions runs lint, tests and scheduled dependency audits once the workflow branch is merged and Actions are enabled.
2. **Task coordination (implemented):** `AGENTS.md` provides instructions for Codex-compatible agents, and the issue template standardizes tasks.
3. **Autonomous coding (not yet connected):** a Codex integration or approved runner must be explicitly configured to pick up issues, write code and open PRs. No such integration is enabled by these files alone.

## Proposed iteration loop
Issue -> human selects priority -> Codex assigned via supported integration -> branch/PR -> CI -> human review -> merge.

## Guardrails
No trading keys; no unattended live trades; no automatic merges. Scheduled checks may fail until dependency installation is configured and the workflow is reviewed.
