# Email Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store inbound Mailgun messages for seven days and expose them in an authenticated dashboard inbox.

**Architecture:** The signed Mailgun webhook will persist messages only for managed identities. A protected FastAPI inbox router will provide list, detail, read-state, and administrator-only deletion. A Celery task removes expired rows daily; Next.js renders the inbox and delegates mutations to a protected proxy.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, PostgreSQL, Alembic, Celery, Next.js App Router, Radix UI, pytest, Vitest.

---

## File structure

- `migrations/versions/p6g7h8i9j0k1_add_email_messages.py`: retention table and indexes.
- `app/tables.py`, `app/models.py`: ORM and API schemas.
- `app/services/email_inbox.py`: persistence, query, read, delete and purge logic.
- `app/webhooks/email.py`, `app/api/email_inbox.py`, `app/main.py`, `app/tasks.py`: ingress, protected API, registration, daily cleanup.
- `front/app/inbox/page.tsx`, `front/app/inbox/[messageId]/page.tsx`: list and detail pages.
- `front/components/EmailMessageControls.tsx`, `front/app/api/operations/email-messages/[messageId]/route.ts`: mutations.
- `front/lib/api.ts`, `front/components/NavLinks.tsx`: typed data client and navigation.
- `tests/test_email_inbox.py`, `front/tests/components.test.tsx`: backend and UI regression tests.

### Task 1: Create retained message storage

**Files:** Create `migrations/versions/p6g7h8i9j0k1_add_email_messages.py`; modify `app/tables.py`; create `tests/test_email_inbox.py`.

- [ ] Write a failing test asserting that `EmailMessage.event_key` is unique and `expires_at` is required.
- [ ] Run `pytest tests/test_email_inbox.py -q` and confirm it fails because `EmailMessage` does not exist.
- [ ] Add `EmailMessage` with UUID id, `identity_id` FK to `email_identities`, unique event key, sender, recipient, subject, plaintext/HTML bodies, received/read/expiry timestamps; create a matching Alembic migration with identity/date and expiry indexes.
- [ ] Run `pytest tests/test_email_inbox.py -q` and `alembic upgrade head`; both pass.
- [ ] Commit: `feat: persist retained email messages`.

### Task 2: Persist signed Mailgun messages idempotently

**Files:** Create `app/services/email_inbox.py`; modify `app/webhooks/email.py`; modify `tests/test_email_inbox.py`.

- [ ] Add failing tests for a signed message sent to an `EmailIdentity`, a duplicated Mailgun event, and an unknown recipient.
- [ ] Run `pytest tests/test_email_inbox.py -q` and confirm the storage assertions fail.
- [ ] Implement `store_inbound_message(event_key, recipient, sender, subject, body_plain, body_html)`. It looks up the normalized identity address, creates `EmailMessage` with `expires_at = now + 7 days`, and returns whether an identity matched. Retain `WebhookEvent` as the idempotency gate. Do not log bodies or verification codes.
- [ ] Extend `POST /webhooks/email` to accept `body-html`, persist known-recipient messages, then retain the existing Redis OTP handling for platform accounts.
- [ ] Run `pytest tests/test_email_inbox.py tests/test_security_regressions.py -q`; all pass.
- [ ] Commit: `feat: retain inbound Mailgun messages`.

### Task 3: Provide protected inbox API

**Files:** Modify `app/models.py`, `app/services/email_inbox.py`, `app/main.py`; create `app/api/email_inbox.py`; modify `tests/test_email_inbox.py`.

- [ ] Add failing tests for authenticated listing, identity/query/unread filters, message detail, marking read, and 403 deletion for an operator.
- [ ] Run `pytest tests/test_email_inbox.py -q`; confirm endpoint tests fail with 404.
- [ ] Add `EmailMessageOut` and paginated `EmailMessagePageOut`; add `GET /api/v1/email-messages`, `GET /api/v1/email-messages/{id}`, `POST /api/v1/email-messages/{id}/read`, and `DELETE /api/v1/email-messages/{id}`.
- [ ] Protect all routes with `require_control_token`; any authenticated dashboard role may list/read/mark read; only `X-Operator-Role: admin` may delete.
- [ ] Run `pytest tests/test_email_inbox.py -q` and check `/openapi.json`; all four routes are present and tests pass.
- [ ] Commit: `feat: add protected email inbox API`.

### Task 4: Enforce seven-day retention

**Files:** Modify `app/services/email_inbox.py`, `app/tasks.py`, `tests/test_email_inbox.py`.

- [ ] Write a failing test with one row expired before `now` and one future row.
- [ ] Run the focused test and confirm `purge_expired_email_messages` is absent.
- [ ] Implement the service using `delete(EmailMessage).where(EmailMessage.expires_at <= now)` and add `purge_expired_email_messages_task` to Celery beat with a 24-hour schedule.
- [ ] Run `pytest tests/test_email_inbox.py -q`; only the expired row is deleted.
- [ ] Commit: `feat: purge retained email messages after seven days`.

### Task 5: Build dashboard list and reader

**Files:** Create `front/app/inbox/page.tsx`, `front/app/inbox/[messageId]/page.tsx`, `front/components/EmailMessageControls.tsx`, `front/app/api/operations/email-messages/[messageId]/route.ts`; modify `front/lib/api.ts`, `front/components/NavLinks.tsx`, `front/tests/components.test.tsx`.

- [ ] Write a failing Vitest asserting that the message control posts a read action and shows confirmation.
- [ ] Run `npm test -- --run tests/components.test.tsx` from `front`; it fails because the component does not exist.
- [ ] Add typed `EmailMessage` and page responses to `front/lib/api.ts`. Render a server-side inbox list with recipient, sender, subject, date, read status, and URL filters. Add a detail page with text body and a sandboxed `iframe srcDoc` HTML preview.
- [ ] Implement the client read/delete control and the Next proxy. The delete button appears only when the server-provided role is admin; backend authorization remains authoritative.
- [ ] Add `/inbox` as `Boite de reception` under `Ressources`.
- [ ] Run `npm test -- --run tests/components.test.tsx`, `npm run lint`, and `npm run build`; all pass.
- [ ] Commit: `feat: add dashboard email inbox`.

### Task 6: Verify and deploy

**Files:** No feature files unless verification finds a scoped defect.

- [ ] Run `pytest -q`, `alembic upgrade head`, `git diff --check`, and the frontend test/lint/build suite.
- [ ] Push `main`; trigger and wait for the Coolify API and dashboard deployments to finish.
- [ ] Verify `https://api.ecovente.com/health`, send a signed staging message to `/webhooks/email`, and retrieve it through the protected inbox endpoint.
- [ ] Confirm the dashboard lists and reads the message, then report the deployment and retention behavior.
