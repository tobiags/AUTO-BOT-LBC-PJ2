# Phone Operations Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified, authenticated phone operations dashboard for temporary OTP reservations and complete SMS history.

**Architecture:** Persist provider reservations in a dedicated `PhoneActivation` table and centralize all lifecycle transitions in `app.services.phone_operations`. Expose a protected FastAPI read/write API, reconcile active reservations through Celery, and render a single protected Next.js control center through a same-origin proxy.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery, PostgreSQL, Next.js 15, React, Radix UI, Vitest, Pytest.

---

### Task 1: Persist temporary number lifecycle

**Files:**
- Create: `migrations/versions/r8i9j0k1l2m3_add_phone_activations.py`
- Modify: `app/tables.py`
- Modify: `app/models.py`
- Test: `tests/test_phone_operations.py`

- [ ] **Step 1: Write the failing model test**

Create a test that imports `PhoneActivation`, instantiates a row with a unique provider order ID, expiry, origin, and status, and validates it through `PhoneActivationOut`.

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phone_operations.py -q`

Expected: import failure because `PhoneActivation` and `PhoneActivationOut` do not exist.

- [ ] **Step 3: Implement the model and migration**

Add the `phone_activations` table with provider/order identity, number, country, service, cost, lifecycle timestamps, optional account/workflow links, OTP text/code, error summary, and indexes on status/expiry/account. Add Pydantic enums and output/page/summary models.

- [ ] **Step 4: Verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phone_operations.py -q`

Expected: model test passes.

### Task 2: Implement lifecycle services and automatic linkage

**Files:**
- Create: `app/services/phone_operations.py`
- Modify: `app/boundaries.py`
- Modify: `app/services/account_creation.py`
- Modify: `app/tasks.py`
- Test: `tests/test_phone_operations.py`
- Test: `tests/test_account_creation.py`

- [ ] **Step 1: Write failing service tests**

Cover these public functions with provider boundaries mocked only at the network boundary:

```python
reserve_phone_activation(country=None, service="leboncoin", origin="manual")
refresh_phone_activation(activation_id)
cancel_phone_activation(activation_id)
reconcile_phone_activations(limit=100)
link_phone_activation(provider_order_id, account_id)
mark_phone_activation_used(provider_order_id)
```

Assert immediate persistence, received OTP transition, local expiry, cancellation, idempotent linkage, and sanitized errors.

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phone_operations.py tests/test_account_creation.py -q`

Expected: failures because the lifecycle service is absent and account creation does not persist provider orders.

- [ ] **Step 3: Implement minimal lifecycle behavior**

Add a non-blocking boundary that fetches the current SMSApp order state. Implement lifecycle transitions in the service. Record/link the acquired order in `create_lbc_account`, mark it used after successful registration, and cancel/mark failed on exceptions. Add a periodic reconciliation Celery task with a bounded batch.

- [ ] **Step 4: Verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phone_operations.py tests/test_account_creation.py -q`

Expected: all targeted tests pass.

### Task 3: Expose protected phone operations API

**Files:**
- Create: `app/api/phone_operations.py`
- Modify: `app/main.py`
- Test: `tests/test_phone_operations_api.py`

- [ ] **Step 1: Write failing API tests**

Test `GET /api/v1/phone-operations/summary`, paginated `activations`, `POST activations`, refresh/cancel actions, filtered `messages`, and CSV export. Assert invalid actions return stable error codes and secrets never appear.

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phone_operations_api.py -q`

Expected: `404` responses because the router is not registered.

- [ ] **Step 3: Implement endpoints**

Use the service layer for mutations, bounded pagination for reads, and `StreamingResponse` for CSV. Register the router with the existing protected dependency in `app/main.py`.

- [ ] **Step 4: Verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests/test_phone_operations_api.py -q`

Expected: all API tests pass.

### Task 4: Build the single-page dashboard

**Files:**
- Create: `front/lib/phone-operations-api.ts`
- Create: `front/app/phones/page.tsx`
- Create: `front/app/api/phone-operations/[...path]/route.ts`
- Create: `front/components/PhoneOperationsControlCenter.tsx`
- Modify: `front/components/NavLinks.tsx`
- Modify: `front/middleware.ts`
- Modify: `front/middleware.test.ts`
- Test: `front/components/PhoneOperationsControlCenter.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Assert `/phones` and `/api/phone-operations` are protected, navigation contains “Téléphonie & SMS”, activation cards render expiry/status/OTP, SMS filters alter requests, and manual reserve/cancel actions update feedback.

- [ ] **Step 2: Verify RED**

Run: `npm test -- --run middleware.test.ts components/PhoneOperationsControlCenter.test.tsx`

Expected: missing routes/component and matcher assertions fail.

- [ ] **Step 3: Implement the page and proxy**

Build a server-loaded page and client control center with overview metrics, tabs for numbers/messages, expiry countdown, copy controls, manual reserve/refresh/cancel, filters, pagination, and CSV download. Add the navigation item and middleware matchers.

- [ ] **Step 4: Verify GREEN**

Run: `npm test -- --run middleware.test.ts components/PhoneOperationsControlCenter.test.tsx`

Expected: targeted frontend tests pass.

### Task 5: Full verification, commit, merge, deploy

**Files:**
- Verify all changed files

- [ ] **Step 1: Run backend quality gates**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check app tests
```

Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 2: Run frontend quality gates**

Run:

```powershell
npm test -- --run
npm run build
```

Expected: all Vitest tests pass and Next.js production build exits `0`.

- [ ] **Step 3: Commit and merge**

Stage only files in this plan, commit on `codex/phone-operations-dashboard`, merge into local `main` without disturbing the user's existing changes, and push `main`.

- [ ] **Step 4: Deploy and verify Coolify**

Deploy API, Celery, and frontend applications. Verify migration success, `/health`, authenticated `/phones`, protected unauthenticated behavior, manual list endpoints, and SMS CSV response. Do not perform a paid number reservation during canary unless the user explicitly requests a real provider transaction.
