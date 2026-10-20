# Cursor VPS access — standing operating workflow

**Decision recorded: 2026-10-20.** The operator has provided Cursor with working SSH access to the shared production VPS. **For FashionRise server tasks, issue VPS commands directly to Cursor in the Cursor assignment instead of asking the operator to repeatedly run and relay shell commands.** This is the preferred workflow for future ChatGPT / Technical PM sessions.

## Who does what

- **ChatGPT / Technical PM:** determine scope, independently review the code and reports, write one complete Cursor assignment with appropriate commands, preflight conditions, safety gates, verification, rollback and stop conditions. Assess Cursor's returned logs and evidence; ask the human only for approvals, secrets or decisions genuinely requiring their participation.
- **Cursor / execution agent:** connect via the already-authorized VPS access; inspect and run permitted FashionRise commands; verify concrete outcomes; report exact revisions, command results (appropriately redacted), health/security checks, anomalies and rollback status. Prefer doing consecutive authorized VPS tasks in a single supervised execution instead of prompting the operator to manually SSH.
- **Human/operator:** give explicit approvals for production changes and handle true external steps, physical-device testing, and private credentials where necessary.

## Permission boundaries and safeguards

- **Working SSH access is not blanket permission to deploy or modify production.** Read-only inspections may proceed when expressly requested. Deployments, service restarts, schema/data changes, infrastructure/security changes, destructive actions and cross-application operations require their own explicit authorization within the task scope.
- **Scope by application:** The VPS is shared. FashionRise work may only touch approved FashionRise paths, its API service and database, and specifically authorized FashionRise Nginx directives. Do not restart or modify PickWise, CureCompass, the synagogue management system, or shared infrastructure incidentally.
- **Secrets:** Credentials were supplied securely to Cursor; never ask the operator to paste private keys/passwords into chat or commit them. Never reveal secrets, full environment files, tokens, connection strings or database credentials in logs. The previous secret named as an SSH private key turned out to be a password; use only its secure configured mechanism, and prefer eventual key-based SSH hardening as a separately approved operation.
- **Reconfirm access and server state each time.** Do not assume a previous Cursor session's credentials or authorization still work. Validate the live revision, checkout cleanliness, service configuration and release path rather than trusting historical server snapshots.
- **Safety-first commands:** avoid force checkouts, deletion/cleanup of unknown files, auto-migrations, broad service restarts and updates to generic deploy scripts. Establish backups and rollback paths before mutating actions. Abort and return for PM review when assumptions or security boundaries differ.
- **Evidence:** Report actions and exact SHAs; distinguish Cursor-reported output from independently verified GitHub facts and from manual device acceptance. Update `docs/00-PROJECT-STATUS.md` after verified milestones.

## Current pinned FashionRise deployment context (historical until reverified)

- WEB-V3A PR #13 merged at `85b6561b338e31c102d101c8d458a1624e7b9f29`; this was the explicitly approved rollout target. Do not silently substitute a newer Git revision for the rollout.
- Preflight reported the live frontend `/var/www/fashionrise/releases/f8a5b22`, backend checkout `6df327ba9c40c2e28faaa04a9a97f97a2b092dd0`, service `fashionrise-api` on loopback port 8010, and Alembic `003` without required migration. These are **observations from a past audit**, not guarantees of current state.
- Production protected by Cloudflare Access, Nginx Authenticated Origin Pulls and explicit private API allowlists. Keep AI, Gallery, public registration and uploads disabled.
- A guarded WEB-V3A frontend+backend deployment has been separately authorized in the Technical PM conversation. **This document is not a new deployment authorization.** Verify actual execution state from Cursor's latest report before taking any further action.

**Next-chat reminder:** Write the full server-execution instructions for Cursor, not for the human to run manually, while retaining the PM approval checkpoint for risky changes.
