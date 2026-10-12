# Security events

A `SecurityEvent` is a durable fact about an authentication action. It does not decide whether an account is compromised or whether a request is allowed. Login, token validation, revocation, and rate limits remain deterministic application logic.

## What the columns mean

- `event_type` names the fact: `LOGIN_FAILED`, `LOGIN_SUCCESS`, `SESSION_CREATED`, `SESSION_REFRESHED`, `SESSION_REVOKED`, or `LOGOUT`.
- `user_id` identifies a known account. It is null when a failed login cannot be matched to a user.
- `login_id` connects events from one successful login across refresh-token rotations. It is a string rather than a foreign key because there is no authentication `sessions` table yet. Legacy tokens may have no device or login context.
- `device_id` points to the browser identifier record in `user_devices` when known. A device is a useful clue, not proof of a physical device or person.
- `ip_address` and `user_agent` preserve request context. Both can change or be misleading.
- `event_data` holds small, structured details such as a linked `login_attempt_id`, `new_device`, a failure reason, or token IDs (`jti`). It must never contain passwords, cookies, or full JWTs.
- `created_at` is set by PostgreSQL when the row is inserted.

`LoginAttempt` retains the submitted email and detailed outcome. `AuditLog` records the application action. `SecurityEvent` supplies a consistent timeline for future investigation. One login may write all three because they serve different queries.

## How events are written

`create_security_event()` adds an ORM object to the current SQLAlchemy session. It does not commit. The controller commits the event alongside the state it describes:

- Failed login: `LoginAttempt` and `LOGIN_FAILED` commit together.
- Successful login: device, successful attempt, audit row, refresh token, `LOGIN_SUCCESS`, and `SESSION_CREATED` commit together.
- Refresh: old-token revocation, replacement token, and `SESSION_REFRESHED` commit together.
- Logout: token revocation, audit row, `SESSION_REVOKED` when a stored refresh token is revoked, and `LOGOUT` commit together.

This avoids an event claiming a successful operation when its database state rolled back.

## Inspect the timeline

Run `docker compose exec postgres psql -U admin -d fintech_agent` from the project directory, then query:

```sql
SELECT created_at, event_type, user_id, login_id, device_id, event_data
FROM security_events
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

A normal sequence for one login is `LOGIN_SUCCESS`, `SESSION_CREATED`, perhaps `SESSION_REFRESHED`, then `SESSION_REVOKED` and `LOGOUT`. A new device is represented by `new_device: true` on the login events. It is evidence for later signal extraction, not a verdict.

The next layer can derive deterministic signals from these rows. It should not let an LLM enforce authentication or account restrictions.