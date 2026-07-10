# AutoTransfert Control Tower Dashboard Design

Date: 2026-07-10
Status: validated design, pending implementation plan

## 1. Business Objective

Turn the existing dashboard into the operational control tower for AutoTransfert. An operator must be able to understand activity, detect blockers, launch and control workflows, inspect external connectors, supervise Leboncoin accounts and sessions, and run isolated browser diagnostics without using a terminal.

The system must process the complete eligible listing backlog, regardless of listing creation date. A listing remains eligible while it has a usable phone number, has not already been contacted by the relevant channel, is not blacklisted, and matches the campaign scope. SMS processing is performed in batches of 200 with automatic continuation.

The dashboard must expose trustworthy counters for:

- collected listings;
- Leboncoin messages sent and received;
- phone numbers extracted from Leboncoin conversations;
- SMS sent and received;
- calls received;
- active accounts and sessions;
- running workflows and remaining backlog;
- connector health, latency, quotas, balances, and errors;
- Browser Use Cloud sessions, tasks, costs, and artifacts;
- experimental Camoufox and Obscura benchmark results.

## 2. Expected Output

The implementation output is a production-ready, responsive dashboard backed by typed FastAPI contracts, persistent workflow state, Celery commands, WebSocket updates, audited operator actions, connector diagnostics, and focused automated tests.

The first screen is the usable control tower. Existing detail pages remain available for listings, campaigns, accounts, and analysis.

## 3. Constraints

- Preserve the existing FastAPI, SQLAlchemy, Celery, Redis, PostgreSQL, Next.js, and Radix UI architecture.
- Make surgical changes and avoid unrelated refactors.
- Never expose API keys, cookies, proxy credentials, OTP values, or complete private conversations to the browser or logs.
- Every command must be idempotent and auditable.
- Destructive or expensive commands require confirmation and an appropriate role.
- A failed experimental engine must never affect the production scraper.
- Browser challenges requiring interaction stop the automated workflow and request intervention. No automatic CAPTCHA bypass is included.
- Access methods, request rates, and endpoints must comply with applicable contracts and terms of access.
- Existing user changes in the dirty worktree must be preserved.

## 4. Inputs, Outputs, and Connected Systems

### Inputs

- search parameters and listing sources;
- campaign templates and campaign/listing assignments;
- active Leboncoin account sessions;
- incoming SMS, call, funds, and Mailgun webhook events;
- Browser Use Cloud task templates and operator-approved custom tasks;
- connector credentials supplied only through server configuration;
- operator commands and confirmations;
- fixed benchmark corpora for Camoufox and Obscura.

### Outputs

- normalized listings and extracted phone numbers;
- outbound Leboncoin messages and SMS logs;
- inbound conversation and webhook events;
- workflow progress, checkpoints, and final results;
- connector health states and actionable alerts;
- Browser Use Cloud live-session links, results, files, screenshots, duration, and cost;
- experimental engine comparison reports;
- immutable audit events for dashboard commands.

### Systems

- PostgreSQL;
- Redis and Celery;
- SMSTools;
- iproxy.online;
- SmsApp.io;
- Mailgun;
- Browser Use Cloud;
- Sentry;
- Patchright;
- Camoufox, behind an experimental feature flag;
- Obscura, in an isolated container;
- Leboncoin and La Centrale, subject to their permitted access conditions.

## 5. Current Baseline

The repository currently provides:

- a Patchright-based Leboncoin scraper using persistent Chromium profiles and rendered-page heuristic extraction;
- a crawl4ai-based La Centrale scraper;
- daily scraping through Celery;
- campaign SMS processing with batches of 200 and automatic requeue while backlog remains;
- account creation through Patchright with Browser Use Cloud as a narrow fallback;
- webhook handlers for SMS, calls, funds, and Mailgun email;
- basic dashboard counters and service balances.

The connector audit performed during design found:

- local PostgreSQL and Redis were unreachable during the probe;
- SMSTools configuration was present, but the read-only SIM-list call failed at connection level;
- the SMSTools webhook secret was absent;
- iproxy configuration was present, but the call returned HTTP 401;
- the iproxy code omits the documented `/connection/{connection_id}` path segment;
- SmsApp.io, Mailgun, and Browser Use Cloud configuration values were present but not yet live-verified;
- Sentry was disabled.

These are blockers to production usability and must be resolved before enabling dashboard commands that depend on them.

## 6. Dashboard Information Architecture

### Header

- dashboard freshness timestamp;
- WebSocket connection state;
- global refresh command;
- primary operation launcher;
- current operator and role.

### Action-Required Band

Show unresolved blockers before ordinary statistics. Each item includes severity, affected workflow, short cause, last occurrence, and a safe next action.

### Activity Metrics

- listings total and today;
- Leboncoin messages sent total and today;
- Leboncoin messages received total and today;
- phone numbers extracted total and today;
- phone extraction conversion rate;
- SMS sent and received;
- SMS response rate;
- calls received.

### Workflow Panel

For every active or paused workflow show:

- workflow type and target;
- current batch and total batches when known;
- current progress and remaining backlog;
- status and last checkpoint;
- elapsed time and estimated completion when meaningful;
- pause, resume, cancel, retry, and detail actions according to role.

### Accounts and Sessions

- active, warming, slowed, blocked, and quarantined account counts;
- current quotas and errors;
- session age and last successful action;
- create, warm, inspect, quarantine, and restore commands;
- direct link to the relevant Browser Use live session when available.

### Connectors and Infrastructure

Show database, Redis, Celery, SMSTools, iproxy, SmsApp, Mailgun, Browser Use, Sentry, and experimental engines. Distinguish:

- not configured;
- configured but unverified;
- live and healthy;
- degraded;
- authentication rejected;
- unavailable.

### Browser Use Cloud

Browser Use Cloud is a transversal automation engine, not only an account-creation fallback. The dashboard supports:

- cloud task and session creation;
- persistent profiles;
- proxy-country selection where supported;
- account creation and warm-up;
- Leboncoin messaging and inbox synchronization;
- complex listing enrichment;
- interface-change diagnostics;
- network and workflow exploration;
- operator-approved custom tasks;
- live browser view;
- stopping, resuming, or retrying tasks;
- result files, screenshots, duration, step count, and cost;
- budget and concurrency alerts.

Capabilities are not artificially limited. Cost, concurrency, roles, domain allowlists, and confirmations are operational guardrails.

### Experimental Lab

Camoufox and Obscura are shown in a dedicated experimental area. They have no automatic production promotion. Controls include start, stop, fixed-corpus test, URL diagnostic, comparison, and report download.

## 7. Data Model

Reuse existing `Listing`, `Campaign`, `SmsLog`, `WebhookEvent`, `PlatformAccount`, and `ServiceBalance` tables.

Add the minimum new persistence required:

### `LbcMessageLog`

- id;
- external message or conversation key;
- listing id;
- account id;
- direction: inbound or outbound;
- status: queued, sent, received, failed, or skipped;
- sanitized preview or content hash;
- phone extracted flag;
- error code;
- created and processed timestamps.

Full conversation content is not stored by default. The normalized phone is stored on `Listing.phone` and the extraction event is retained for metrics.

### `WorkflowRun`

- id and idempotency key;
- workflow type;
- target type and id;
- status;
- current and total progress;
- batch number and batch size;
- Celery task id;
- checkpoint data;
- sanitized last error;
- started, updated, and finished timestamps;
- initiating actor.

### `ConnectorStatus`

- connector name;
- status;
- configured flag;
- latency;
- last successful check;
- last check;
- normalized error code;
- safe error summary;
- quota or balance summary when available.

### `AuditEvent`

- actor and role;
- action;
- target;
- idempotency key;
- sanitized input summary;
- result status;
- workflow run id;
- timestamp.

Obscura and Camoufox diagnostics initially use `WorkflowRun` with structured checkpoint/result data. A dedicated benchmark table is added only if retained history cannot be queried efficiently from these runs.

## 8. Workflow Architecture

The dashboard issues a typed command to FastAPI. FastAPI validates role, state, configuration, confirmation, and idempotency. It records an audit event and workflow run before enqueueing a Celery task. Celery executes bounded batches, persists checkpoints, and emits progress events. The dashboard receives WebSocket updates and can always reconstruct current state from PostgreSQL after reconnecting.

### Complete Listing Backlog

Campaign eligibility is based on contact state, phone availability, blacklist state, and campaign scope, not listing creation date. Fetch `batch_size + 1`, process only `batch_size`, keep the campaign running when another eligible item exists, and requeue the next batch. Preserve cumulative counters.

### Leboncoin Messaging

1. Select eligible listings and healthy accounts under quota.
2. Send an outbound message through an approved browser session.
3. Persist the outbound result idempotently.
4. Periodically synchronize inbox conversations because no supported Leboncoin webhook is available in this project.
5. Persist new inbound messages idempotently.
6. Extract and normalize phone numbers.
7. Associate the number with the listing and update dashboard counters.
8. Prevent duplicate contact across retries and channels according to campaign policy.

### Collection Engines

The current Patchright implementation remains the initial production reference.

- Full browser path: production reference for permitted JavaScript navigation and persistent sessions.
- Camoufox path: canary behind a feature flag and isolated profiles.
- HTTP fast path: optional canary only after endpoint stability and access authorization are established; it must be rate-limited and reversible.
- Obscura: isolated benchmark and diagnostics only until evidence supports a broader role.
- Browser Use Cloud: available across collection, navigation, enrichment, messaging, account operations, and diagnostics where its adaptive behavior adds value.

No design assumes a fixed DataDome cookie TTL or that transferring one cookie guarantees a valid session. Browser and network session consistency must be measured rather than assumed.

## 9. Normal Scenarios

- collect all matching old and new listings;
- deduplicate listings by stable source URL/identifier;
- process SMS in consecutive batches;
- send and synchronize Leboncoin conversations;
- extract phone numbers and expose conversion metrics;
- create and warm accounts;
- execute Browser Use Cloud templates and supervised custom tasks;
- receive idempotent webhooks;
- resume workflows from checkpoints;
- compare experimental engines on a fixed corpus;
- display live progress and final results.

## 10. Error Scenarios

- 401/403 authentication failure: no automatic retry; pause and request configuration correction;
- 429: honor `Retry-After`, then bounded exponential backoff with jitter;
- timeout or 5xx: bounded retry, then circuit breaker;
- insufficient credit or quota: pause with next safe resume time;
- expired Leboncoin session: quarantine account and stop its tasks;
- interactive challenge: stop automation and request intervention;
- unusual rise in block/challenge rate: open the collection circuit;
- Redis unavailable: reject new commands and show degraded state;
- PostgreSQL unavailable: block commands and render the last safe snapshot if available;
- webhook duplicate: return success without duplicate side effects;
- WebSocket disconnect: reconnect and reload persisted state;
- Browser Use budget threshold: warn, then stop new expensive tasks at a configurable hard limit;
- experimental engine failure: stop only the experimental run.

## 11. Retry, Logging, and Alerts

- Classify every error before deciding to retry.
- Retry only transient network, 429, and 5xx failures.
- Use bounded exponential backoff with jitter.
- Persist checkpoints before scheduling the next batch.
- Correlate logs with workflow id, batch id, listing id, account id, and connector.
- Redact secrets, proxy credentials, cookies, OTPs, and message bodies.
- Send critical production errors to Sentry once configured.
- Push actionable alerts through WebSocket and persist them for reload.
- Include a safe diagnostic recommendation with every actionable connector failure.

## 12. Permissions

- Viewer: read dashboards, results, health, and history.
- Operator: launch approved templates, pause/resume ordinary workflows, inspect live sessions.
- Admin: configure operational limits, run custom Browser Use tasks, rotate IP, manage experimental engines, and perform destructive actions.

Authentication uses a secure HttpOnly session. Browser clients never receive provider API keys. Sensitive actions require explicit confirmation and generate an audit event.

## 13. Test Strategy

### Unit

- dashboard counter calculations;
- workflow state transitions;
- permissions and confirmations;
- idempotency keys;
- error classification and retry decisions;
- phone extraction and message metrics;
- connector status mapping.

### Integration

- PostgreSQL, Redis, and Celery command flow;
- checkpoint and resume between batches;
- connector read-only health probes;
- webhook idempotency;
- Browser Use task/session wrapper using mocked provider contracts;
- WebSocket disconnect and reload.

### Contract

- versioned provider request and response fixtures;
- documented iproxy connection path;
- Browser Use Cloud task, session, webhook, and cost payloads;
- SMSTools, SmsApp, and Mailgun payload validation.

### End-to-End

- desktop and mobile dashboard rendering;
- launch, confirm, pause, resume, and inspect workflow;
- role restrictions;
- live progress;
- unavailable API and degraded infrastructure states;
- no secret present in HTML, JavaScript payloads, logs, or screenshots.

### Experimental Benchmarks

- fixed public/permitted URL corpus;
- success rate;
- duration and throughput;
- memory;
- rendered-data completeness;
- JavaScript and network errors;
- challenge/block rate;
- estimated cost per 1,000 successful listings.

## 14. Recommended Delivery Order

1. Repair and live-verify core connectors and local infrastructure.
2. Add typed workflow, connector, audit, and messaging persistence.
3. Add dashboard read models and action-required states.
4. Add authenticated, idempotent workflow commands.
5. Add Browser Use Cloud as a complete module and dashboard surface.
6. Add Leboncoin messaging synchronization and counters.
7. Add Camoufox canary and Obscura Lab.
8. Add optional HTTP fast-path experiment only after access validation.
9. Run failure simulations, E2E checks, and responsive visual verification.

## 15. Quality Criteria

- Every displayed number has a documented source of truth.
- Every dashboard command is typed, authorized, idempotent, auditable, and tested.
- No experimental failure can interrupt production workflows.
- No secret reaches the frontend or logs.
- Old and new eligible listings are processed without duplicate contact.
- Mobile and desktop layouts remain readable without overlap.
- Connector status distinguishes configured from live-verified.
- Tests reproduce failures before fixes and pass after implementation.
- Completion is claimed only after fresh test, lint, build, and relevant runtime evidence.

## 16. Self-Verification Checklist

Before each implementation phase is marked complete, verify:

- the change maps directly to a validated requirement;
- the failing test was observed before production code changed;
- focused tests pass;
- broader regression tests pass;
- lint and type checks pass;
- the dashboard works at desktop and mobile sizes;
- no sensitive value appears in outputs;
- error and degraded states are visible;
- retries are bounded and do not retry permanent failures;
- documentation and operator guidance match actual behavior;
- remaining risks are explicitly reported.

## 17. Ready-to-Copy Implementation Prompt

```text
Role:
Act as a senior full-stack and automation engineer responsible for implementing the AutoTransfert control tower safely in the existing repository.

Context:
The repository uses FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery, Next.js, Radix UI, Patchright, Browser Use Cloud, SMSTools, iproxy, SmsApp, Mailgun, and Sentry. Existing behavior and uncommitted user work must be preserved. Follow docs/superpowers/specs/2026-07-10-control-tower-dashboard-design.md as the approved source of truth.

Inputs:
- the current repository and its tests;
- the approved design specification;
- server-side environment configuration without exposing values;
- official current provider documentation;
- the existing dashboard screenshot and design conventions.

Method:
1. Inspect the current implementation and dirty worktree.
2. Identify the smallest coherent implementation phase.
3. Reproduce each missing behavior with a failing test.
4. Implement only enough production code to pass that phase.
5. Preserve current architecture and existing behavior.
6. Add typed API contracts, idempotency, audit, error classification, bounded retries, structured logs, and actionable alerts where required.
7. Keep Browser Use Cloud broadly usable across account, messaging, navigation, enrichment, diagnostics, and supervised custom tasks.
8. Keep Camoufox and Obscura isolated behind feature flags until benchmarks justify promotion.
9. Never expose secrets or implement automatic CAPTCHA bypass.
10. Verify focused tests, full regression tests, lint, type checks, builds, and responsive UI screenshots.

Output format:
- outcome summary;
- problem addressed and root cause;
- files changed;
- implementation decisions and alternatives rejected;
- tests and exact results;
- current connector status;
- remaining risks;
- next recommended phase.

Quality criteria:
- minimal justified changes;
- no unrelated refactor;
- every metric has a source of truth;
- every command is authorized, idempotent, auditable, and tested;
- failures are visible and recoverable;
- no secret reaches frontend, logs, tests, or screenshots;
- no success claim without fresh verification evidence.

Self-check before reporting completion:
- Did every new behavior have a failing test first?
- Are permanent errors excluded from retries?
- Can workflows resume safely after interruption?
- Are old and new eligible listings both processed?
- Are Browser Use sessions, costs, and tasks visible and controllable?
- Are experiments isolated from production?
- Did all required verification commands complete successfully?
```

## 18. How to Adapt the Prompt

- For a narrow bug fix, replace the implementation scope with one workflow or connector and retain all quality gates.
- For a dashboard-only phase, keep backend contracts mocked but require responsive screenshots and frontend tests.
- For a connector phase, require official documentation, read-only live probes, redacted output, and contract fixtures.
- For Browser Use Cloud, provide the exact approved task templates, cost ceiling, domains, and required result schema.
- For Camoufox or Obscura, provide a fixed permitted corpus and comparison thresholds; never point an experimental run at production sessions.
- For deployment, add infrastructure-specific health checks, migration verification, rollback steps, and post-deploy canaries.
