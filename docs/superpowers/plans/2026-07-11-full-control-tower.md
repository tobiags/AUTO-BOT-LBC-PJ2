# Full Control Tower Implementation Plan

**Source of truth:** `docs/superpowers/specs/2026-07-10-control-tower-dashboard-design.md` and `docs/Plan_Implementation_Modules.html`.

**Goal:** Deliver every validated operational module as a real, testable dashboard surface backed by typed FastAPI commands, persistent state, Celery execution, audit history, and production verification.

## Non-negotiable constraints

- Keep the existing FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery, Next.js, and Radix architecture.
- Process listing backlogs in bounded, resumable batches, including old and new listings.
- Never expose provider secrets to the browser.
- Persist every operator command before enqueueing it and require an idempotency key.
- Do not automate CAPTCHA solving or bypass access controls. Browser challenges pause for operator intervention.
- Keep Camoufox and Obscura isolated and disabled by default.
- Deploy API, worker, and frontend sequentially and verify each before continuing.

## Lot 1 - Command and audit plane

- Add operator roles and a server-side admin token/session boundary.
- Add typed command endpoints for workflow start, pause, resume, cancel, retry, connector probe, and iProxy rotation.
- Persist `WorkflowRun` and `AuditEvent` before dispatch.
- Add idempotency, state validation, structured error codes, and focused tests.

## Lot 2 - Provider operations

- iProxy: configuration, proxy state, rotation command, latency, last success, and errors.
- SMSTools: SIM inventory, quotas, balance, webhook state, sending window, and test diagnostics.
- SmsApp: balance/configuration, number-order lifecycle, polling diagnostics, cancellation, and errors.
- Mailgun/calls/webhooks: configuration state, delivery history, idempotency, and operator diagnostics.
- Add connector detail APIs and a dedicated dashboard page.

## Lot 3 - Listing and messaging workflows

- Backfill old and new listings using resumable cursor-based batches.
- Track LBC outbound/inbound messages and extracted phone numbers.
- Expose campaign and collection progress, pause/resume/cancel/retry, checkpoints, and errors.
- Keep legal windows, quotas, blacklist/STOP behavior, retries, logs, and alerts.

## Lot 4 - Browser Use Cloud

- Wrap the documented API v2 for tasks, sessions, efficient status polling, task details, files, screenshots, live URLs, stop, and cost.
- Provide approved templates for navigation, enrichment, messaging assistance, account operations, and diagnostics.
- Allow supervised custom tasks with domain allowlists and cost ceilings.
- Persist task metadata/results in `WorkflowRun` and audit every command.
- Add webhook/poll reconciliation and dashboard history/detail pages.

## Lot 5 - Experimental lab

- Create isolated module directories and runtime paths for Camoufox and Obscura.
- Add feature flags, fixed-corpus benchmarks, URL diagnostics, start/stop, comparison, and report export.
- Never reuse production profiles or automatically promote an experimental engine.
- Pause and surface operator intervention for browser challenges.

## Lot 6 - Complete dashboard

- Add routes for Operations, Workflows, Messaging, Browser Use, Connectors, Accounts, and Lab.
- Add functional icon buttons, confirmations, loading/error/success states, tooltips, logs, history, costs, artifacts, and freshness timestamps.
- Preserve existing listings, campaigns, accounts, and analyzer pages.
- Verify responsive desktop/mobile layouts with populated and failure states.

## Lot 7 - Completion gates

- Backend and frontend test suites, lint, production build, migration head, and offline SQL.
- Provider contract tests with mocked responses and read-only live probes where credentials permit.
- Code review against both validated source documents.
- Sequential production deployment and public endpoint/browser verification.
- Revoke the temporary Coolify token after final production acceptance.
