# Email Identity Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a dashboard-managed pool of real inbound domain identities with generated French names and atomic internal reservation.

**Architecture:** Add a dedicated `email_identities` table rather than overloading platform accounts. An identity service owns generation and state transitions; protected API routes expose batch generation and lifecycle actions. The dashboard renders the identity pool separately from platform accounts.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic, Next.js 15, React, Radix UI, Vitest, pytest.

---

### Task 1: Persistent identity pool and service

**Files:**
- Create: `migrations/versions/o5f6a7b8c9d0_add_email_identities.py`
- Modify: `app/tables.py`, `app/models.py`
- Create: `app/services/email_identities.py`
- Test: `tests/test_email_identities.py`

- [ ] Write tests for a generated French name, unique domain email, and available-to-reserved transition.
- [ ] Run `pytest tests/test_email_identities.py -q` and observe failures.
- [ ] Add the schema, migration, Pydantic contracts, and transactional service.
- [ ] Re-run `pytest tests/test_email_identities.py -q`.

### Task 2: Protected management API

**Files:**
- Create: `app/api/email_identities.py`
- Modify: `app/main.py`
- Test: `tests/test_email_identity_api.py`

- [ ] Write API tests for listing, batch sizes 10/15/20, duplicate-safe generation, and admin-only mutations.
- [ ] Run `pytest tests/test_email_identity_api.py -q` and observe failures.
- [ ] Add `/api/v1/email-identities` list, batch generation, and lifecycle command routes.
- [ ] Re-run `pytest tests/test_email_identity_api.py -q`.

### Task 3: Dashboard management surface

**Files:**
- Modify: `front/lib/api.ts`, `front/app/accounts/page.tsx`
- Create: `front/components/EmailIdentityControls.tsx`
- Modify: `front/tests/components.test.tsx`, `front/tests/handlers.ts`

- [ ] Write UI tests for lot generation controls and identity display/copy.
- [ ] Run `npm test -- --run tests/components.test.tsx` and observe failures.
- [ ] Implement the API proxy, client control, and dashboard identity table.
- [ ] Run `npm run lint`, `npm test`, `npm run build`, and `pytest -q`.
- [ ] Commit, push, apply migration through the API deployment, then deploy API and front in Coolify.
