# Project

A minimal backend service that accepts payment provider webhooks and turns confirmed
payments into active user subscriptions. A single `POST /webhook/payment` endpoint
records the payment and activates (or renews) the user's subscription for 30 days,
safely under retried/duplicate webhook deliveries.

---

# Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2.x (async, `asyncpg`)
- Alembic
- Docker

---

# Architecture

```
app/
  api/        FastAPI routers (HTTP layer only)
  services/    business logic (process_payment_webhook)
  models/      SQLAlchemy ORM entities
  schemas/     Pydantic request/response contracts
  core/        settings
  db/          engine/session
```

**Why no separate Repository layer.** The write path is one operation: given a
confirmed payment, upsert a `payments` row and upsert the matching `subscriptions`
row, in one transaction. A repository here would just wrap two `INSERT ... ON
CONFLICT` statements with no second caller and no query reuse — it would be an
abstraction with nothing to abstract. `app/services/webhook.py` talks to
SQLAlchemy directly; if a second write path or read-heavy queries show up later,
extracting a repository at that point is cheap.

**Why the transaction.** Both writes (`payments` insert, `subscriptions` upsert)
happen inside a single `async with session.begin()` block. That makes "payment
row exists, subscription was never activated" structurally impossible: either both
writes commit, or neither does. There is no window — not even a crash between two
separate commits — where the payment is recorded but the subscription update never
happened.

**Why `ON CONFLICT` (`INSERT ... ON CONFLICT`) instead of `SELECT` then
`INSERT`/`UPDATE`.** A check-then-write pattern (`SELECT ... ; if not found:
INSERT`) has a race: two concurrent deliveries of the same webhook can both pass
the `SELECT` before either commits, and both attempt to `INSERT`. Postgres's
`ON CONFLICT` pushes the uniqueness check into the database itself, so the second
of two concurrent inserts is resolved atomically by the constraint instead of by
application logic that can race.

**Why `UNIQUE(payment_id)`.** `payment_id` is the idempotency key the payment
provider guarantees is stable across retries. The uniqueness lives in the database
as a constraint, not as an application-level check, so it holds even under
concurrent duplicate deliveries. `on_conflict_do_nothing(index_elements=["payment_id"])`
turns a duplicate delivery into a no-op detected via `rowcount == 0`.

**Why `subscriptions` is updated inside the same transaction as the payment
insert.** So the two facts ("this payment was received" and "this user's
subscription is active until X") change together. If the subscription update
happened in a separate transaction after the payment commit, a crash in between
would leave a payment on record with no corresponding subscription — an
inconsistent state that would require reconciliation logic to detect and fix.
Doing both in one transaction removes the need for that logic entirely.

**Why the webhook is idempotent, and why that matters.** Payment providers deliver
webhooks at-least-once — they retry on timeout, on non-2xx responses, on no
response at all. The handler treats `payment_id` as the identity of the event: the
first delivery inserts the payment and activates the subscription; every
subsequent delivery of the same event hits `ON CONFLICT DO NOTHING`, returns
`"already_processed"`, and does **not** re-run the subscription upsert. Duplicate
deliveries are safe by construction — the response differs (`processed` vs.
`already_processed`) but the database state after N deliveries of the same event
is identical to after 1.

**Why it's not possible to end up with "payment exists, subscription doesn't".**
That state would require the payment insert to commit while the subscription
upsert is skipped or fails silently. Because both statements run inside one
`session.begin()` block, any failure after the payment insert rolls the payment
insert back too — there is no code path that persists one without the other.

---

# Running

```bash
docker compose up
```

Apply migrations (in a second terminal, once the `db` service is healthy):

```bash
docker compose exec backend alembic upgrade head
```

The API is then available at `http://localhost:8000` (`uvicorn`, started by the
`backend` container).

For local (non-Docker) development:

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

---

# API

## `POST /webhook/payment`

Request:

```json
{
  "payment_id": "pay_demo_001",
  "user_id": 1,
  "amount": 4900,
  "status": "CONFIRMED"
}
```

Response (first delivery):

```json
{ "payment_id": "pay_demo_001", "result": "processed" }
```

Response (duplicate delivery of the same `payment_id`):

```json
{ "payment_id": "pay_demo_001", "result": "already_processed" }
```

Response (`status` other than `CONFIRMED`, e.g. `PENDING`):

```json
{ "payment_id": "pay_demo_002", "result": "ignored" }
```

## `GET /health`

```json
{ "status": "ok" }
```

Interactive docs (Swagger UI) at `GET /docs`.

---

# SQL task

[`query.sql`](query.sql) — users with an active subscription who have no
`meetings_attendance` record in the last 30 days.

---

# Design decisions

**Why these models.** `users`, `payments`, `subscriptions` map 1:1 onto the
domain facts the webhook needs: who paid, what was paid, and what access that
payment grants. `payments` is an append-only ledger of provider events;
`subscriptions` is current-state derived from that ledger (one row per user,
overwritten on renewal) — modeling them as two tables keeps "what happened" and
"what's true right now" separate instead of inferring current access by
scanning the payment history on every request.

**Why this transaction boundary.** The boundary is exactly the set of writes that
must be all-or-nothing from the caller's point of view: one payment event in,
one subscription state out. Nothing outside that (e.g. the HTTP response
serialization) needs to be inside the transaction, and nothing inside it could be
safely split into two transactions without reintroducing the inconsistent-state
problem described above.

**Why these constraints.** `UNIQUE(payment_id)` on `payments` is the idempotency
guarantee. `UNIQUE(user_id)` on `subscriptions` encodes the business rule "a user
has at most one subscription" directly in the schema, which is what makes
`ON CONFLICT (user_id) DO UPDATE` a correct upsert instead of an approximation of
one. `CHECK (amount > 0)` and the `gt=0`/`min_length=1` Pydantic validators reject
malformed provider payloads before they reach the database.

---

# Known limitations

- No webhook signature verification — the endpoint trusts any caller that can
  reach it. A production version would verify a provider-supplied signature
  header before processing the payload.
- No authentication/authorization on any endpoint.
- No automated test suite.
- `subscriptions.expires_at` is always reset to "now + 30 days" on a confirmed
  payment; there's no proration or stacking logic for renewals made before the
  current period ends.
- `app/api/v1/` is mounted with no endpoints under it — reserved for future
  versioned routes, currently dead weight.
