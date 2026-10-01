# AI Fintech Operations Lab

Registration saves a pending user and an email outbox row in PostgreSQL. A
separate worker claims one pending row at a time, sends it to Mailpit, and
records delivery state in PostgreSQL. It immediately claims the next eligible
email while work is available, and waits two seconds when the queue is empty.

To run the local email flow:

```sh
docker compose up -d --build postgres redis mailpit
docker compose build api email_worker
docker compose run --rm api uv run alembic upgrade head
docker compose up -d api email_worker
```

Register through `POST http://localhost:8000/api/v1/register` with an email and
password. Open Mailpit at `http://localhost:8025` to see the message. The
verification link opens a confirmation page; clicking its button submits the
token to the API.

Use `docker compose logs -f email_worker` to inspect worker errors. The worker
needs the database migration before it can query `email_outbox`.

The worker retries delivery failures up to five total attempts with an
increasing delay. A claim left in `processing` for more than five minutes is recovered by
the worker. Delivery is at least once: if SMTP accepts a message and the worker
crashes before recording `sent`, the message may be delivered again after the
claim lease expires. Queue counts and oldest pending age are logged every
minute.

To run four worker containers against the same PostgreSQL queue:

```sh
docker compose up -d --scale email_worker=4 email_worker
```

Workers claim rows with PostgreSQL `FOR UPDATE SKIP LOCKED`, so they can process
different messages concurrently. For production sending, configure a real SMTP
provider and its sending limits; Mailpit is for local development.
