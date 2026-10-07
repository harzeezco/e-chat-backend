# AI Fintech Operations Lab — Logout, Revocation & Security Monitoring

## 1. Purpose

Logout ends the browser's authenticated session and revokes the credentials that the server can identify. In this project, logout is also an important security event: it records the end of a credential lifecycle and contributes evidence to background monitoring.

Logout must remain deterministic. The API revokes tokens and clears cookies. A future agent may study logout patterns and raise an alert, but it must not disable accounts, revoke other credentials, or change payment access.

---

## 2. Problem Being Solved

Deleting a cookie only removes that credential from one browser. A copied token can still be presented to the API until the backend rejects it. A secure logout therefore needs server-side revocation as well as browser cookie deletion.

The system also needs an answer to:

* Which user or credential ended the session?
* Was the access token revoked?
* Was the refresh token revoked?
* Did the database commit those changes?
* Can monitoring correlate logout with prior logins and later payment events?

---

## 3. Current Logout Flow

The logout endpoint is `POST /api/v1/auth/logout`, implemented in `app/auth/controllers/logout.py`.

```text
Logout Request
      ↓
Read access_token and refresh_token cookies
      ↓
Validate each token independently
      ↓
Revoke active refresh-token database row
      ↓
Insert access-token jti into revoked_access_tokens
      ↓
Commit database changes
      ↓
Add USER_LOGOUT audit event
      ↓
Clear both browser cookies
```

The refresh cookie is scoped to `/api/v1/auth`, so it can be sent to both refresh and logout routes. The access cookie is scoped to `/`.

Invalid or expired cookies should not prevent local cookie deletion. A token that is already expired cannot pass JWT validation, so it does not need a new revocation entry.

---

## 4. Revocation Models

### 4.1 RefreshToken

The refresh token's `jti` is stored in `refresh_tokens`. Rotation marks the old record's `revoked_at` and links it to its replacement. Logout marks the current active refresh record revoked so it cannot obtain additional access tokens.

The refresh endpoint takes a row lock while consuming the token. This helps prevent two simultaneous requests from successfully rotating the same refresh-token row.

### 4.2 RevokedAccessToken

Logout inserts the access JWT's `jti` and expiry into `revoked_access_tokens`. `get_current_user` checks for that `jti` after validating the JWT and rejects it if the record exists.

The revocation entry is retained only as long as it is useful. A cleanup process should remove entries after the corresponding access JWT expiry; that cleanup has not yet been implemented.

---

## 5. Cookie Clearing and Revocation Are Different

Cookie deletion tells the browser to stop sending its copy. Server-side revocation tells the API to reject a copied token.

Both cookie deletions must use the same names and paths used when cookies were created:

* `access_token` — `/`
* `refresh_token` — `/api/v1/auth`

If a cookie is created with one path and deleted with another, the browser may keep the original cookie.

The current access-token denylist revokes the access token presented during logout. An earlier access token from a previous refresh cycle may still be usable until its short expiry. Revoking every access token in one logical login session requires a shared session/family identifier.

---

## 6. Audit Evidence

The intended logout audit event is `USER_LOGOUT`. It can record:

* Verified user ID, if either token identifies one
* Request IP address and User-Agent, when available
* Whether a valid access token was presented
* Whether a valid refresh token was presented
* Event timestamp

Never put raw JWTs, passwords, or secret values into audit data. The `AuditLog` model supports a nullable `user_id`, so an unauthenticated logout request can be recorded without inventing an actor identity.

### Current transaction issue

The current controller commits token revocations before calling `create_audit_log`. The audit service only adds the row to the SQLAlchemy session; it does not commit. There is no later commit in the current logout controller, so the `USER_LOGOUT` audit row is not currently persisted.

The intended transaction boundary is to add the audit event before the same commit that persists token revocations:

```text
Refresh revocation
+ Access-token revocation
+ Logout audit event
        ↓
One database transaction and commit
```

This makes the audit evidence agree with the revocation outcome. If the database transaction fails, the API should not claim that revocation and auditing succeeded.

---

## 7. Deterministic Security and Agentic Monitoring

Logout is enforced synchronously by application code:

* Validate token signatures and types.
* Update refresh-token revocation state.
* Persist access-token revocation state.
* Clear the browser cookies.

The planned monitoring process is asynchronous:

```text
Committed USER_LOGOUT event
      ↓
Durable outbox/event feed
      ↓
Separate security worker
      ↓
Correlate login, refresh, logout, and future payment events
      ↓
Create an alert with supporting evidence
      ↓
Human review
```

The agent may identify patterns such as rapid login/logout cycles across many accounts, unusual sequences of refresh and logout events, or activity inconsistent with a user's recent history. It may raise a finding; it must not revoke credentials, disable users, authorize transactions, or block the logout request.

The worker must not receive signing keys or unrestricted database write access. Its event input should be structured and minimized. If it is unavailable, logout and deterministic revocation must continue to work, and queued evidence must wait for later processing.

---

## 8. Reliability and Transaction Design

The audit service adds an `AuditLog` row to the caller's SQLAlchemy session and leaves transaction ownership to the caller. Logout therefore owns the transaction for revocation and audit state.

When the background security worker is built, use a transactional outbox or equivalent durable event mechanism. The logout event and outbox entry should commit with the revocations. This prevents a committed security action from disappearing from the monitoring feed if the process stops between database commit and queue publication.

Audit history should represent facts. Queue retry state, worker leases, and processing attempts belong in separate operational fields or tables rather than mutating historical audit facts.

---

## 9. Security Data and Operational Boundaries

* JWTs are signed, not encrypted; never log or place raw tokens in event data.
* IP addresses and User-Agent values are sensitive security evidence and need access and retention controls.
* A security finding is an observation for review, not an authorization decision.
* Payment authorization, ownership, limits, approvals, and idempotency remain deterministic server-side rules.
* The agent cannot edit `users`, `refresh_tokens`, `revoked_access_tokens`, or payment state.

---

## 10. Current Gaps and Follow-up Work

* Move `create_audit_log` before the logout transaction commit so the `USER_LOGOUT` row is persisted atomically with revocation.
* Cookie flags currently use `secure=False`, appropriate only for local HTTP. Use `Secure` on HTTPS deployments.
* Add a shared session/family identifier if logout must revoke all access tokens from that logical login session, including older access JWTs.
* Detect refresh-token reuse at the token-family level; current rotation rejects an old token but does not revoke its replacement chain.
* Add cleanup for expired access-revocation and refresh-token rows.
* Add CSRF protections for state-changing cookie-authenticated routes.
* Build the durable security-event outbox, separate worker, finding storage, and human review workflow. The existing email worker only delivers email and is not the security monitor.

---

## 11. Engineering Lessons

1. Clearing browser state is not the same as revoking a credential.
2. Revocation checks make otherwise stateless access JWTs depend on server-side state.
3. Audit evidence should commit with the security action it describes.
4. A background agent can keep security operations observant without controlling access.
5. A separate container is useful isolation, but least-privilege data and database permissions are still required.

