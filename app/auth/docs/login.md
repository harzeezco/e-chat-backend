# AI Fintech Operations Lab — Login, Authentication & Security Monitoring

## 1. Purpose

This document explains the login flow, the security evidence it records, and how the project intends to use background agentic operations to study activity after signup.

The goal is not to make login depend on an AI model. Login is a sensitive boundary: deterministic application code must decide whether credentials are valid, the account is active, and a request may receive credentials.

The agentic layer is intended to keep the security operation active after registration. It will study recorded activity in the background and raise evidence-backed findings for review. It will not approve or deny logins, suspend users, revoke credentials, or initiate payment actions.

---

## 2. Problem Being Solved

A basic backend often records a user at signup and then treats authentication as a simple password check. That leaves important questions unanswered:

* Were there repeated failed login attempts?
* Did a successful login follow an unusual sequence of failures?
* Is one IP address attempting many accounts?
* Did a login happen from a new client context?
* Was an account pending, inactive, or suspended when access was attempted?
* What happened immediately before or after a sensitive payment operation?

The backend needs a reliable history of security-relevant events. A background worker can then inspect that evidence without adding slow or probabilistic logic to the login request itself.

---

## 3. Architectural Boundary

The request path remains deterministic:

```text
Login Request
      ↓
Input Validation and Rate Limit
      ↓
Password Verification
      ↓
Current Account Status Check
      ↓
Persist Login Attempt and Audit Evidence
      ↓
Issue Tokens OR Return a Denial
```

The monitoring path is asynchronous:

```text
Persisted Security Event
      ↓
Durable Event Queue / Outbox
      ↓
Separate Security Worker
      ↓
Pattern Analysis and Evidence Correlation
      ↓
Security Finding / Alert for Review
```

The monitoring worker is allowed to analyze a constrained event feed and create findings. It is not an authorization service. It must not change a user's status, revoke tokens, or alter payment state.

> Deterministic code enforces access. The agent investigates activity and raises issues.

---

## 4. Current Login Flow

The current login endpoint is registered at `POST /api/v1/auth/login` and implemented in `app/auth/controllers/login.py`.

```text
Request
  ↓
Capture client IP and User-Agent
  ↓
Apply Redis IP rate limit
  ↓
Create LoginAttempt record
  ↓
Check password input and find user
  ↓
Verify password hash
  ↓
Require ACTIVE account
  ├─ Failure → Save unsuccessful LoginAttempt → Return error
  └─ Success → Save successful LoginAttempt
                 ↓
          Create access and refresh JWTs
                 ↓
          Add USER_LOGIN audit event
          Add refresh-token database record
                 ↓
          Commit and set HttpOnly cookies
```

The login code verifies passwords using the stored password hash. It does not put passwords into JWT claims or audit event data.

---

## 5. Evidence Records

### 5.1 LoginAttempt

`app/auth/models/login_attempt.py` records the result of a login attempt, including:

* Submitted email
* Client IP address, when available
* User-Agent, when available
* Success flag
* Failure reason
* Creation timestamp

This table is specialized evidence for login outcomes. Failed login paths currently save a `LoginAttempt`; successful login also saves one.

### 5.2 AuditLog

`app/auth/models/audit_log.py` records system events. A successful login creates a `USER_LOGIN` event with the user ID, IP address, User-Agent, role, and account status.

At present, failed logins are represented in `LoginAttempt`; they do not also create `AuditLog` events. The future monitoring pipeline must explicitly consume login attempts as well as audit events, or add a durable event/outbox record for both outcomes.

### 5.3 RefreshToken

`app/auth/models/refresh_token.py` stores the refresh JWT's `jti`, owner, expiry, revocation time, and replacement link. The JWT stays in an HttpOnly browser cookie; the database record lets the server reject refresh tokens that were revoked or already rotated.

---

## 6. Access and Refresh Tokens

The token service in `app/auth/services/jwt_access_token.py` creates two JWT types:

* **Access token:** short-lived credential sent to normal API routes.
* **Refresh token:** longer-lived credential sent to the refresh endpoint to obtain new tokens.

Both carry a subject (`sub`), unique token ID (`jti`), token type, issue and expiry times, issuer, and audience. The server checks the signature and expected claims. A refresh token must not be accepted as an access token.

Login sets both tokens as `HttpOnly` cookies. The refresh cookie is scoped to `/api/v1/auth`, so the browser sends it to refresh and logout routes but not unrelated API paths. Tokens are not returned in the JSON response.

JWTs are signed, not encrypted. Claims must not contain passwords, secrets, payment data, or other sensitive payloads.

---

## 7. Transaction and Failure Evidence

The login attempt is committed before the credential decision returns. On success, the `USER_LOGIN` audit event and refresh-token record are added and committed before the response cookies are returned.

The intended rule is:

> Persist evidence and the state that evidence describes at an explicit transaction boundary.

If the database commit for the successful login fails, the application should not return tokens whose refresh-token state was not stored. If a later monitoring queue is added, the event/outbox record should be written in the same database transaction as its source evidence so the worker cannot miss a committed login event.

---

## 8. Rate Limiting and Account Status

Login currently uses a Redis rate limiter with a limit of five requests per 60-second window keyed by client IP. The database records the attempt separately; Redis counters are temporary enforcement state, while `LoginAttempt` is historical evidence.

The login flow checks account status after password verification. Pending and other non-active accounts do not receive tokens. Protected requests also load the current user from the database, so a later suspension can invalidate access even before a JWT expires.

IP addresses from `request.client.host` are trustworthy only for the connection as observed by the API. Forwarded-IP headers must only be honored when supplied by configured trusted proxies.

---

## 9. Security Data Boundaries

The system should record enough evidence to investigate activity, while minimizing sensitive data:

* Never store or emit raw passwords, access JWTs, refresh JWTs, verification tokens, or secret keys in logs or agent input.
* Treat email, IP address, and User-Agent as sensitive personal/security data with access controls and retention rules.
* Prefer stable identifiers and structured event fields over free-form dumps.
* Give the monitoring worker only the event data it needs; it does not need authentication secrets or write access to users, tokens, or payments.

---

## 10. Planned Background Security Operations

The current `email_worker` is for email delivery. It is not a security-monitoring agent. A separate security worker is planned.

The planned worker should:

1. Consume durable login, logout, token, and future payment events.
2. Correlate events over a bounded time window.
3. Produce a finding containing the signal, supporting event IDs, confidence, and time range.
4. Store or deliver the finding for a human operator to review.
5. Continue operating independently if the API is busy, and retry safely after failures.

The agent should not be in the login request path. It should not decide whether a login is valid, lock an account, or revoke a token. If the worker is down, deterministic login and authorization rules must continue to work and the durable event backlog must remain available for later processing.

The preferred reliability pattern is a transactional outbox: write the business/security evidence and an event-to-process in one database transaction, then let the separate worker claim and process events. Do not overload the audit table with mutable worker-queue state; audit history and work-queue state have different purposes.

---

## 11. Current Gaps and Follow-up Work

* Login failure reasons are persisted, but the unknown-user branch currently labels the reason `User already exist`; the wording should describe the actual failure.
* Failed login events are not currently written to `AuditLog`; the future worker must consume `LoginAttempt` records or receive a dedicated outbox event.
* Cookie settings currently use `secure=False` for local HTTP. HTTPS deployments must set `Secure`.
* A background security worker, event outbox, finding model, retention policy, and operator review flow have not yet been implemented.
* Login uses IP-based rate limiting; additional controls such as account-aware throttling, MFA/step-up authentication, and trusted-proxy configuration need deliberate design before production payment use.
* User role and ownership enforcement must remain on the API server for every protected endpoint. Frontend state and agent findings do not grant permission.

---

## 12. Engineering Lessons

1. A login decision must be deterministic and repeatable.
2. A successful password check is not enough; current account status still matters.
3. Security evidence and enforcement state serve different purposes.
4. Persist events before asking an asynchronous worker to analyze them.
5. A monitoring agent can make the system more observant without becoming an access-control authority.
6. Never place the AI model between the user and a critical authentication decision.

