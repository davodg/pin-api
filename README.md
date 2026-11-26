# Pin-api

**English** | [Português (Brasil)](README.pt-BR.md)

This API performs CRUD operations on a PostgreSQL database. The sections below describe each endpoint.

## Requirements

- Python
- Docker

## Authentication and authorization

The demo represents a single organization and should use only fictional data.
All `/api/v1/feedback` endpoints require `Authorization: Bearer <token>`.

| Role | GET | POST / PUT / PATCH / DELETE |
| --- | --- | --- |
| `viewer` | Allowed | Forbidden |
| `admin` | Allowed | Allowed |

`/`, `/health`, `/docs`, and `/openapi.json` are public. The login endpoint is `POST /auth/token`.
Missing credentials, an invalid or expired token, or a disabled user result in
`401`; insufficient permissions result in `403`. The user's role and status are
read from the database on every request. There is no public registration, refresh
token, or logout with individual token revocation: tokens expire after 15 minutes.
Disabling a user immediately revokes their access; changing `JWT_SECRET`
invalidates all tokens.

### Initial setup

1. Copy `.env.example` to `.env` and configure `DB_*` for your PostgreSQL instance.
2. Generate a random secret and set `JWT_SECRET` in `.env` (do not commit the value):

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. Install dependencies and apply migrations, including the users table:

   ```bash
   python -m pip install -r requirements.txt
   dotenv run -- alembic upgrade head
   ```

4. Create users; the password prompt hides input and requires 12–128 characters:

   ```bash
   python -m app.create_user --username demo --role viewer
   python -m app.create_user --username administrator --role admin
   ```

The command does not overwrite existing users. Passwords are stored as Argon2id
hashes; hashing and verification run outside the event loop. The application
refuses to start without a `JWT_SECRET` of at least 32 bytes. With Docker, run
migration and user creation commands inside the `pin-api` service using
`docker compose exec pin-api ...`, after configuring `.env` and starting the database.

### Login and usage

Send JSON to `POST /auth/token`:

```json
{"username": "demo", "password": "your-password"}
```

The response contains `access_token`, `token_type: "bearer"`, and `expires_in: 900`.
In Swagger (`/docs`), log in and paste `access_token` into **Authorize**.
Add `-H "Authorization: Bearer $TOKEN"` to the curl examples below.

Login allows 10 attempts per IP within a 60-second window, including successful
logins. The limit is persisted in PostgreSQL and shared across workers; exceeding
it returns `429` with `Retry-After: 60`. Records older than one day are removed
during new attempts. Behind a proxy, configure the ASGI server to trust only your
proxy's IP addresses; do not trust forwarded headers from arbitrary clients.
Users sharing the same IP also share this limit.

For a public deployment, configure HTTPS on the proxy or hosting platform, keep
the `admin` account private, and share only the `viewer` account with fictional
data. This repository does not configure HTTPS. The current policy allows reading
all feedback records in the organization; it does not implement tenant isolation
or record ownership authorization.

## Creation idempotency

`POST /api/v1/feedback` and `POST /api/v1/feedback/batch` require the
`Idempotency-Key` header. Generate one key per operation (a UUID is recommended)
and reuse it for every retry of that operation. Keys accept 1–128 characters:
ASCII letters, digits, periods, hyphens, `_`, and `:`. Missing or invalid keys
result in `422`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: 752e2068-fdad-4385-a95c-b6427d43692c" \
  -H "Content-Type: application/json" --data-binary @feedback.json
```

- Same key, user, and payload: returns the original `200` status and JSON,
  even if the feedback has since been updated or deleted.
- Same key and user, but a different payload: `409 Conflict`.
- Different users have independent key namespaces.
- Pydantic validates payloads before SHA-256 hashing. JSON object key order does
  not matter; omitted optional fields are equivalent to their defaults.
- Records are retained for 24 hours after the response is stored. Replays do not
  extend this period. Reusing an expired key may create another feedback record.
- The reservation, feedback, and response are written in the same transaction.
  Failures before commit roll everything back and allow retrying with the same key.
- Concurrent requests wait for PostgreSQL locks. The lock wait limit is 3 seconds;
  exceeding it returns `503` with `Retry-After: 1`. Retry with the same key instead
  of generating a new one.
- Authentication and authorization are checked on every attempt, before replay.
  Validation errors and error responses are not stored.

Apply migration `0004` with `dotenv run -- alembic upgrade head` before deploying
the updated version. The table stores a copy of the feedback in its JSONB response;
apply the same access and backup controls as for the rest of the database.

To remove expired responses, run periodically:

```bash
python -m app.cleanup_idempotency
```

Cleanup deletes batches of up to 1,000 records, skips rows locked by active
requests, and does not delete feedback records. No schedule is created
automatically. Logical expiration works even before physical cleanup.
Different keys do not prevent business-level duplicates. PUT, PATCH, and DELETE
do not use this replay mechanism.

## Feedback validation

Pydantic models document the payload in `/docs` and reject invalid input with
`422` before executing SQL. POST and PUT require `name`, `email`,
`corporate_email`, `department`, `location`, `company_tenure`, `gender`,
`generation`, and all eight scores (`interest_in_position`, `contribution`,
`learning_and_development`, `feedback`, `manager_interaction`,
`opportunity_clarity`, `permanence_expectation`, `enps`).

- Required text fields cannot be empty and must respect column length limits.
- Email addresses are validated; unknown fields and `id` in the body are rejected.
- Scores must be JSON integers, without coercion from strings, booleans, or decimals.
  Bounds match PostgreSQL INTEGER; no questionnaire score scale has been defined.
- Input and output dates use `YYYY-MM-DD`. The previous `DD/MM/YYYY` format is no
  longer accepted. The existing TIMESTAMP column is retained; the API exposes a date.
- Path identifiers and the `id` filter must be valid UUIDs.

This validation change does not require a database migration. Existing records
must satisfy the response contract, including valid email addresses and required
text fields. Clients that previously sent partial PUT requests must switch to PATCH.

## Endpoints

### POST /api/v1/feedback

Creates a record in the `employee_feedback` table. Requires `Idempotency-Key`
as described in the idempotency section.

**Example body (JSON):**

```json
{
  "name": "Demo 019",
  "email": "demo019@pinpeople.com.br",
  "phone_number": "11912488394",
  "corporate_email": "demo019@pinpeople.com.br",
  "department": "human resources",
  "location": "manaus",
  "company_tenure": "between 2 and 5 years",
  "gender": "other",
  "generation": "generation y",
  "l0_company": "company",
  "l1_directorate": "directorate a",
  "l2_management": "management a1",
  "l3_coordination": "coordination a11",
  "l4_area": "area a111",
  "response_date": "2022-01-20",
  "interest_in_position": 7,
  "interest_in_position_comments": "-",
  "contribution": 1,
  "contribution_comments": "-",
  "learning_and_development": 5,
  "learning_and_development_comments": "-",
  "feedback": 1,
  "feedback_comments": "-",
  "manager_interaction": 3,
  "manager_interaction_comments": "-",
  "opportunity_clarity": 4,
  "opportunity_clarity_comments": "-",
  "permanence_expectation": 7,
  "permanence_expectation_comments": "-",
  "enps": 8,
  "enps_comments": "The company encourages innovation and creativity."
}
```

**Example response:**

```json
{
  "data": {
    "id": "d39033df-88af-4d46-a3a4-a56776e17a66",
    "name": "Demo 019",
    "...": "..."
  },
  "meta": {}
}
```

---

### POST /api/v1/feedback/batch

Creates **1 to 100 feedback records** in a single transaction and returns the
result in the same request. Requires the `admin` role and a valid `Idempotency-Key` header.

The body is `{"items": [...]}`: each object must satisfy the same `FeedbackCreate`
model as the individual POST. Minimal example of a batch containing one item:

```json
{
  "items": [
    {
      "name": "Person A",
      "email": "person.a@example.com",
      "corporate_email": "person.a@company.com",
      "department": "Engineering",
      "location": "São Paulo",
      "company_tenure": "1 year",
      "gender": "Other",
      "generation": "Generation Y",
      "interest_in_position": 7,
      "contribution": 7,
      "learning_and_development": 7,
      "feedback": 7,
      "manager_interaction": 7,
      "opportunity_clarity": 7,
      "permanence_expectation": 7,
      "enps": 8
    }
  ]
}
```

Save it as `batch.json` and send:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/feedback/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: 59404415-383b-443d-9279-95a8fc15e306" \
  -H "Content-Type: application/json" --data-binary @batch.json
```

The `200` response contains IDs in input order, with zero-based indexes:

```json
{
  "data": [
    {"index": 0, "id": "d39033df-88af-4d46-a3a4-a56776e17a66"}
  ],
  "meta": {"created": 1}
}
```

- The entire batch is validated before any writes. An invalid item returns `422`
  with its position and field, such as `body.items.2.email`; no items are created.
- An error during any insertion or while saving the response rolls back the
  **entire batch**, including the key reservation. There is no partial success.
- The same key, user, and batch return the original response for 24 hours.
  Changing items **or their order** with the same key returns `409`.
- The `feedback:batch-create:v1` operation has a separate key namespace from
  individual creation. The same key on both endpoints represents two operations.
- Lock wait limits and `503`/`Retry-After` responses follow the existing idempotency
  policy. Resend the entire batch with the same key.
- Idempotency applies to the whole batch. Resending a subset or using another key
  may create duplicates. Identical items within a batch are created separately.

No additional migration is required: batch creation reuses the table from
migration `0004`. Integration tests also cover concurrent batches, ID ordering,
the maximum batch size, and rollback after a failure on the second item.

---

### GET /api/v1/feedback

Lists records with **pagination** and **filters**.

**Main query parameters:**

- `page` (default: 1)
- `limit` (default: 10)
- `id`
- `name`, `email`, `corporate_email`, `department`, `location`, `gender`, `generation`
  (case-insensitive **substring** text filters)
- `response_date_from`, `response_date_to` (dates)
- Numeric ranges:
  - `enps_min`, `enps_max`
  - `interest_in_position_min`, `interest_in_position_max`
  - `contribution_min`, `contribution_max`
  - `learning_and_development_min`, `learning_and_development_max`
  - `feedback_min`, `feedback_max`
  - `manager_interaction_min`, `manager_interaction_max`
  - `opportunity_clarity_min`, `opportunity_clarity_max`
  - `permanence_expectation_min`, `permanence_expectation_max`

**Examples:**

- Pagination:
  ```
  GET /api/v1/feedback?page=1&limit=20
  ```
- Text and date:
  ```
  GET /api/v1/feedback?department=resources&response_date_from=2024-01-01&response_date_to=2024-12-31
  ```
- `enps` range:
  ```
  GET /api/v1/feedback?enps_min=7&enps_max=10
  ```

**Example response:**

```json
{
  "data": [
    { "id": "d39033df-88af-4d46-a3a4-a56776e17a66", "name": "Demo 019", "...": "..." },
    { "id": "78245992-4564-4c71-b4b7-05ede27d341b", "name": "Demo 314", "...": "..." }
  ],
  "meta": { "page": 1, "limit": 5, "total": 12, "pages": 3 }
}
```

---

### PUT /api/v1/feedback/{id}

Replaces the entire record. Send all required fields using the same body as POST.
Omitted nullable fields are set to `null`. For a partial update, use PATCH.
The identifier must be a valid UUID.

Save the complete POST example as `feedback.json` and run:

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/feedback/d39033df-88af-4d46-a3a4-a56776e17a66 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" --data-binary @feedback.json
```

### PATCH /api/v1/feedback/{id}

Updates only the supplied fields and returns the complete updated record.
Omitted fields are preserved. Send `null` to clear a comment, phone number,
organizational level, or date. Required fields do not accept `null`.
An empty object, unknown fields, or an attempt to change `id` returns `422`.
Only `admin` can use PATCH.

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/feedback/d39033df-88af-4d46-a3a4-a56776e17a66 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Updated Demo","enps":9,"feedback_comments":null}'
```

PUT, PATCH, and DELETE return `404` when the record does not exist.
Responses retain the `{"data": ..., "meta": {}}` envelope.

---

### DELETE /api/v1/feedback/{id}

Deletes a record by `id`.

**Response:**

```json
{ "data": { "id": "d39033df-88af-4d46-a3a4-a56776e17a66" }, "meta": {} }
```

---

## Pagination, filters, and sorting

- **Pagination:** `page >= 1` and `1 <= limit <= 100` (defaults: 1 and 10).
- **Filters:** see the list under [GET /api/v1/feedback](#get-apiv1feedback).
  Text filters use `ILIKE '%value%'` in PostgreSQL.
- **Sorting:** defaults to `response_date DESC NULLS LAST, id DESC`.

---

## Running tests

From the **`pin-api/`** directory, with your **virtual environment activated**:

```bash
python -m unittest discover -s tests -v
```

To set up from scratch:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt httpx
python -m unittest discover -s tests -v
```

> Tests use asynchronous mocks and `fastapi.testclient`, without requiring a database.

PostgreSQL access uses Psycopg 3 with `AsyncConnectionPool`, opened during the
FastAPI lifespan and closed on shutdown. Each worker has its own pool of 4 to 16
connections. Startup waits for available connections and fails if the database is
unavailable. Each operation uses a pooled connection, committing on success and
rolling back on error. Configure the connection through `DB_USER`, `DB_PASSWORD`,
`DB_HOST`, `DB_PORT`, and `DB_NAME`.

## Running the project

Install dependencies:

```bash
pip install -r requirements.txt
```

Make the startup script executable:

```bash
chmod +x start-docker-and-migrate.sh
```

Run the script to start the API Docker container and create the database tables:

```bash
./start-docker-and-migrate.sh
```

## How AI was used in this project

Copilot was used for repetitive tasks. ChatGPT was also used for debugging,
creating the shell script, and improving the README.

## Idempotency integration tests

Unit tests do not require PostgreSQL. To also run concurrency and rollback tests,
use **a disposable database whose name starts with `pin_test_`**, configure `DB_*`
for that database, and apply migrations first:

```bash
# DB_* must point exclusively to the disposable database.
alembic upgrade head
PIN_API_INTEGRATION=1 python -m unittest tests.test_idempotency_integration -v
```

The suite creates test users and feedback records and removes them when finished.
Do not run it against a database containing real data. Tests cover replay,
conflicts, user isolation, failures between writes, concurrent expiration,
timeouts, and cleanup.
