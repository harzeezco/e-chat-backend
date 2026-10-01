# AI Fintech Operations Lab — Architecture, Security & Business Decisions

## 1. Project Purpose

This project is being built to understand and demonstrate how a realistic fintech backend works beyond simply writing features.

The objective is to build a system that combines:

* Backend engineering
* Authentication and authorization
* Database design
* Transaction management
* Security
* Auditability
* Fintech business workflows
* Operational investigation
* AI agent workflows

The long-term goal is an **AI-assisted operational investigation system for fintech platforms**.

The central problem is not:

> "How do I build a chatbot?"

The problem is:

> "How can an engineer or operations team understand what happened when something goes wrong in a complex financial system?"

For example:

> "I sent ₦2 million. My account was debited, but my beneficiary hasn't received the money."

Answering this properly may require looking at:

* Customer
* Account
* Transaction
* Ledger
* Provider transfer
* Webhook
* Settlement
* Reconciliation
* Security events
* Audit history

The project therefore focuses on building the underlying system and evidence first, then placing an investigation agent on top of it.

---

# 2. Architectural Philosophy

The project follows this general security and business architecture:

```text
Request
   ↓
Authentication
   ↓
Authorization
   ↓
Risk / Security Context
   ↓
Business Rules
   ↓
Controlled Operation
   ↓
Audit / Monitoring
```

The eventual AI investigation workflow is:

```text
Customer Complaint
        ↓
Authentication / Identity Context
        ↓
Evidence Gathering
        ↓
Read-Only Investigation
        ↓
Evidence Correlation
        ↓
Reasoning
        ↓
Gated Action OR Escalation
        ↓
Audit
```

One of the most important architectural decisions is:

> The LLM is not the security boundary.

The deterministic application remains responsible for enforcing:

* Authentication
* Authorization
* Rate limiting
* Input validation
* Database constraints
* Business rules
* Approval requirements
* Session controls
* Audit requirements

The AI system operates inside these boundaries.

---

# 3. Why We Are Building the Foundation Before the Agent

It would be easy to start with an LLM and expose tools such as:

```text
get_customer()
get_transaction()
search_logs()
```

However, this would hide the real engineering problem.

An investigation agent can only produce reliable conclusions if the underlying system produces reliable evidence.

For example, if we don't record:

* Registration attempts
* Login attempts
* Sessions
* IP addresses
* User agents
* Security events
* Account changes
* Transaction history
* Provider events
* Ledger events
* Webhooks

then the agent cannot reliably reconstruct what happened.

Therefore the project is intentionally being built from the foundation upward:

```text
Database
   ↓
Identity
   ↓
Authentication
   ↓
Sessions
   ↓
Security Evidence
   ↓
Auditability
   ↓
Business Operations
   ↓
Investigation Tools
   ↓
Investigation Agent
   ↓
Operator UI
```

This forces us to understand the actual system instead of hiding complexity behind an AI model.

---

# 4. Current Registration Architecture

The current registration flow is:

```text
Registration Request
        ↓
Capture Request Context
        ↓
Rate Limit
        ↓
Create Registration Attempt
        ↓
Check Existing User
        ↓
Hash Password
        ↓
Create User
        ↓
Database Integrity Protection
        ↓
Create Audit Event
        ↓
Commit Transaction
        ↓
Return Safe Response
```

There are three deliberately different concepts.

## 4.1 User

The `users` table represents the **current state of an account**.

Examples:

* User ID
* Email
* Password hash
* Role
* Status

---

## 4.2 RegistrationAttempt

The `registration_attempts` table represents **what happened during registration attempts**.

Examples:

* Email
* IP address
* User agent
* Success/failure
* Failure reason
* Timestamp

This answers:

> "What happened when someone tried to register?"

---

## 4.3 AuditLog

The `audit_logs` table represents **important events that happened in the system**.

Examples:

```text
USER_REGISTERED
USER_LOGIN_SUCCESS
USER_LOGIN_FAILED
PASSWORD_CHANGED
SESSION_CREATED
SESSION_REVOKED
ROLE_CHANGED
PAYMENT_CREATED
PAYMENT_APPROVED
PAYMENT_FAILED
```

This answers:

> "What important event happened in the system?"

These concepts are intentionally separate.

---

# 5. Problem Encountered: Application Validation vs Database Integrity

The registration flow first checks whether an email already exists:

```python
existing_user = session.scalar(
    select(User).where(User.email == data.email)
)
```

This is useful, but it cannot be the final protection against duplicate users.

Two requests could theoretically happen concurrently:

```text
Request A → check email → doesn't exist
Request B → check email → doesn't exist

Request A → insert user
Request B → insert user
```

Therefore the database must also enforce a unique constraint.

## Decision

Application validation is useful for normal application behavior, but the database must remain the final integrity boundary.

## Lesson

> Application checks improve the flow; database constraints enforce final integrity.

This principle applies far beyond registration.

---

# 6. Problem Encountered: IntegrityError and Rollback

One of the important problems encountered was understanding transaction rollback.

The registration attempt is created before the user:

```python
session.add(attempt)
```

Suppose user creation fails because of a database integrity constraint:

```python
IntegrityError
```

A normal:

```python
session.rollback()
```

rolls back the current transaction.

That means the registration attempt could also disappear.

This is problematic because a failed registration attempt can itself be valuable security evidence.

The system would effectively lose evidence of the failure.

---

# 7. Solution: Database Savepoint

The solution is to isolate user creation inside a nested transaction/savepoint:

```python
with session.begin_nested():
    session.add(user)
    session.flush()
```

Conceptually:

```text
Outer Transaction
│
├── RegistrationAttempt
│
└── Savepoint
      │
      └── User INSERT
             │
             ├── Success
             │
             └── Failure
                    ↓
              Rollback Savepoint
                    ↓
              Preserve Attempt
                    ↓
              Record Failure
                    ↓
              Commit Evidence
```

The savepoint allows the failed user creation to be rolled back without destroying the surrounding registration evidence.

## Engineering lesson

> Transaction design is part of security and business correctness.

This is not merely a SQLAlchemy implementation detail.

The transaction boundary determines whether the system can preserve the evidence required to understand failures.

---

# 8. Why `flush()` Is Used

We learned the difference between:

```python
session.flush()
```

and:

```python
session.commit()
```

`flush()` sends pending SQL operations to the database so constraints can be evaluated, but it does not commit the entire transaction.

This allows the application to detect database errors while retaining control over the outer transaction.

The flow becomes:

```text
Create Registration Attempt
        ↓
Try User INSERT
        ↓
Flush
        ↓
Database checks constraints
        ↓
Success OR IntegrityError
        ↓
If failure → rollback savepoint
        ↓
Record failure
        ↓
Commit evidence
```

This is an example of using database transaction semantics intentionally rather than treating `commit()` and `rollback()` as generic error-handling commands.

---

# 9. Audit Logging Decision

The audit service does not commit the transaction itself.

Instead:

```python
create_audit_log(...)
```

adds an audit event to the current SQLAlchemy session.

The registration route controls the transaction boundary.

This allows:

```text
User
+
RegistrationAttempt
+
AuditLog
        ↓
One successful transaction
```

The desired behavior is that a successful registration creates all required records together.

The audit service therefore should not independently call:

```python
session.commit()
```

because that would make transaction ownership unclear and could produce inconsistent states.

## Decision

> Lower-level services add changes to the current transaction; the operation that owns the workflow controls the commit.

---

# 10. Why Registration Attempts and Audit Logs Are Both Needed

At first glance these tables may appear redundant.

They are not.

## Registration Attempt

Answers:

> "What happened during a registration attempt?"

It is specialized security/operational evidence.

Example:

```text
email
IP
user-agent
success
failure_reason
timestamp
```

## Audit Log

Answers:

> "What important event happened in the system?"

It is system-wide event history.

Example:

```text
user
action
resource
resource_id
IP
user-agent
event_data
timestamp
```

A successful registration can therefore create both:

```text
registration_attempt
success = true
```

and:

```text
audit_log
action = USER_REGISTERED
```

The apparent duplication is intentional because the records serve different operational purposes.

---

# 11. Security Decision: Password Hashing

Passwords should never be stored directly.

The flow is:

```text
Password
   ↓
Password Hashing
   ↓
Password Hash
   ↓
Database
```

The original password should never be stored.

This protects credentials if the database is exposed.

---

# 12. Security Decision: TLS / HTTPS

Password hashing protects credentials **at rest**.

TLS protects data **in transit**.

These solve different problems.

Conceptually:

```text
Client
   ↓
HTTPS / TLS
   ↓
Application
   ↓
Password Hash
   ↓
Database
```

Security therefore has multiple layers rather than one mechanism that solves everything.

---

# 13. Security Decision: Authentication vs Authorization

Authentication answers:

> Who are you?

Authorization answers:

> What are you allowed to do?

A valid session does not automatically mean that a user can perform every action.

For example:

```text
Authenticated Customer
        ↓
Can access own account
        ↓
Cannot automatically change another customer's account
        ↓
Cannot automatically approve payments
        ↓
Cannot automatically change privileged configuration
```

This separation is fundamental to the architecture.

---

# 14. Security Decision: Rate Limiting

Registration is protected with Redis-based rate limiting.

Conceptually:

```text
Request
   ↓
Rate Limiter
   ↓
Allowed?
 ┌───────┴───────┐
No               Yes
↓                 ↓
429            Registration
```

Redis is appropriate for temporary operational state such as counters.

Permanent business/security evidence belongs in the database.

The rate limiter therefore serves a different purpose from `registration_attempts`.

Redis answers:

> "Should this request be allowed right now?"

The database answers:

> "What happened historically?"

---

# 15. Security Decision: IP Address Handling

The application currently captures:

```python
request.client.host
```

This works for the current development environment.

However, in production the application may sit behind:

* Reverse proxy
* Load balancer
* CDN
* Cloudflare
* API gateway

In that situation, `request.client.host` may represent the proxy rather than the original client.

Headers such as:

```text
X-Forwarded-For
X-Real-IP
```

must therefore only be trusted from configured/trusted proxies.

We should never blindly trust client-supplied forwarding headers.

## Lesson

> Security data is only useful when we understand how it was obtained.

---

# 16. Security Decision: User-Agent

The User-Agent is captured because it provides investigation context.

It can help correlate:

```text
Account
   ↓
Login
   ↓
IP
   ↓
User-Agent
   ↓
Session
   ↓
Transaction
```

However, User-Agent should be treated as evidence, not proof of identity.

---

# 17. Business Domain Model

The project is intentionally being designed around real fintech operations rather than generic CRUD.

A financial workflow may involve:

```text
Customer
   ↓
Account
   ↓
Funding
   ↓
Balance
   ↓
Payment
   ↓
Provider
   ↓
Settlement
   ↓
Ledger
   ↓
Beneficiary
   ↓
Reconciliation
```

This matters because a customer-facing problem can originate in any part of the workflow.

For example:

> "I sent ₦2 million, my account was debited, but my beneficiary hasn't received the money."

The investigation might need to ask:

```text
Was the transaction created?
        ↓
Was the account debited?
        ↓
Was the ledger entry posted?
        ↓
Was a provider transfer created?
        ↓
Did the provider accept the transfer?
        ↓
Was the webhook received?
        ↓
Was the beneficiary credited?
        ↓
Was reconciliation completed?
```

This is a business investigation problem, not simply an API problem.

---

# 18. Why the Agent Is an Investigation System, Not a Chatbot

The agent should not simply answer:

> "Your payment is probably delayed."

It should gather evidence.

For example:

```text
Customer
   ↓
Transaction
   ↓
Ledger
   ↓
Provider Transfer
   ↓
Webhook
   ↓
Reconciliation
```

Then it should construct a timeline and explain the state of the operation.

The intended capability is:

> **Business-domain investigation.**

The agent understands the vocabulary and relationships of the fintech system.

---

# 19. Why the Agent Should Not Be Responsible for Network Security

Network and infrastructure security should remain deterministic.

Examples:

```text
TLS
WAF
Rate Limiting
Firewall
Network Access Control
Connection Controls
Input Validation
Database Permissions
```

These systems should not depend on an LLM deciding whether a network request is safe.

The investigation agent has a different responsibility.

It can correlate evidence such as:

```text
Registration
+
Login
+
IP
+
Device
+
Session
+
Security Events
+
Transactions
```

and investigate suspicious patterns or customer problems.

## Decision

> The agent investigates security and business evidence; deterministic infrastructure enforces first-line security controls.

---

# 20. Why Arbitrary SQL Is Not the Intended Agent Interface

It would be technically easy to give the agent database access and allow it to generate arbitrary SQL.

That is not the intended architecture.

Instead, the agent should use controlled domain tools such as:

```text
get_customer()
find_transactions()
get_transaction()
get_ledger_entries()
get_provider_transfer()
get_webhook_events()
get_audit_logs()
get_registration_attempts()
```

Each tool has a defined purpose.

This provides:

* Better security
* Better auditability
* Easier testing
* Better evaluation
* Predictable behavior
* Domain-specific vocabulary
* Easier permission control

The agent should interact with the business domain, not directly manipulate the database.

---

# 21. Investigation Architecture

The intended investigation workflow is:

```text
Customer Complaint
        ↓
Identity / Authentication Context
        ↓
Investigation Request
        ↓
Read-Only Evidence Gathering
        ↓
Customer Data
+
Transaction Data
+
Ledger Data
+
Provider Data
+
Webhook Data
+
Security / Audit Data
        ↓
Evidence Correlation
        ↓
Reasoning
        ↓
Resolution
      /     \
Safe Action  Escalation
```

The important property is that the agent should explain its conclusion using evidence.

It should not generate a plausible answer without evidence.

---

# 22. Current Development Strategy

The project is deliberately being built in stages.

Instead of:

```text
LLM
 ↓
Tools
 ↓
Demo
```

we are building:

```text
Security Foundation
        ↓
Database Evidence
        ↓
Business State
        ↓
Operational History
        ↓
Investigation Tools
        ↓
Agent
        ↓
UI
```

This approach forces us to learn the underlying systems.

It demonstrates knowledge of:

* Backend engineering
* Databases
* SQL transactions
* Authentication
* Authorization
* Security
* Auditability
* Fintech workflows
* AI agents
* Operational tooling

rather than simply demonstrating LLM API usage.

---

# 23. Current Progress

## Phase 1 — Security and Identity Foundation

Completed:

* User model
* Registration
* Password hashing
* Registration attempts
* Redis rate limiting
* Database integrity protection
* Audit log model
* Audit log service
* Successful registration audit event

Next:

* Login
* Sessions
* Session revocation
* Login attempts
* Security events

---

# 24. Next Phase — Minimal UI

After completing the authentication foundation, build a small UI for:

* Registration
* Login
* Authenticated session
* Basic user state

The purpose is not to build a polished frontend immediately.

The purpose is to:

1. Connect the backend to a real client.
2. Test the authentication flow.
3. Break it intentionally.
4. Observe failures.
5. Fix them.
6. Improve the architecture based on real behavior.

---

# 25. Fintech Operations Phase

Build realistic domain models for:

* Customers
* Accounts
* Transactions
* Ledger entries
* Providers
* Beneficiaries
* Webhooks
* Reconciliation
* Payment states

This will create the data foundation for the investigation agent.

---

# 26. Investigation Tools Phase

Expose controlled read-only tools such as:

```text
get_customer()
find_transactions()
get_transaction()
get_ledger_entries()
get_provider_transfer()
get_webhook_events()
get_audit_logs()
get_registration_attempts()
```

The tools should have clear boundaries and predictable outputs.

---

# 27. Investigation Agent Phase

The agent architecture should follow:

```text
Authenticate
     ↓
Investigate
     ↓
Reason
     ↓
Gated Action OR Escalate
```

The agent should initially focus on investigation rather than unrestricted action.

This reduces risk and makes evaluation easier.

---

# 28. Operator UI Phase

Eventually build an internal interface where an operator can ask:

> "Why hasn't this beneficiary received the ₦2 million?"

The system should return something like:

```text
Investigation
────────────────────────────

Customer:
Acme Trading Ltd

Transaction:
TXN-100001

Amount:
₦2,000,000

Account:
Debited

Ledger:
Debit posted

Provider:
Transfer accepted

Webhook:
Received

Beneficiary:
Not confirmed credited

Current finding:
Provider accepted the transfer but beneficiary
credit has not been confirmed.

Next step:
Escalate / investigate provider settlement.
```

The exact UI will evolve as the underlying data model becomes more complete.

---

# 29. What Makes This Project Different

The project is not trying to demonstrate:

> "I built an AI chatbot."

The intended demonstration is:

> "I built the foundations for an AI-powered operational investigation system that understands fintech business workflows, preserves security evidence, uses controlled tools, and respects deterministic authorization and audit boundaries."

The agent is only one component.

The deeper system is:

```text
Business Domain Knowledge
        +
Security Model
        +
Operational Evidence
        +
Controlled Tools
        +
Policy
        +
Agent Reasoning
        +
Auditability
```

---

# 30. Engineering Principles Established So Far

## Principle 1 — Database constraints are the final integrity boundary

Application validation cannot replace database constraints.

## Principle 2 — Transactions are part of business correctness

Commit and rollback decisions determine whether state and evidence remain consistent.

## Principle 3 — Security evidence must survive failures

A failed operation can be more valuable to an investigator than a successful operation.

## Principle 4 — Authentication and authorization are different

Knowing who someone is does not determine what they are allowed to do.

## Principle 5 — AI is not the security boundary

Deterministic systems enforce security.

## Principle 6 — AI should operate through controlled tools

The agent should not have unrestricted production access.

## Principle 7 — Business state and historical evidence are different

Current state belongs in business models.

Historical activity belongs in appropriate attempt/event/audit structures.

## Principle 8 — Observability is part of the product

A system that cannot explain what happened is difficult to operate and support.

## Principle 9 — Build the domain before the agent

The quality of the agent depends heavily on the quality of the evidence underneath it.

## Principle 10 — Business understanding matters as much as implementation

For every important technical decision, ask:

```text
Why does this data exist?
Who uses it?
What business decision depends on it?
What happens if it is wrong?
What security risk does it introduce?
How would an operator investigate a failure?
```

---

# 31. Business Engineering Mindset

One of the main goals of this project is to move beyond thinking:

> "I was given a feature, so I wrote the code."

Instead, the engineering process should begin with:

```text
Business Problem
      ↓
Operational Workflow
      ↓
Required Evidence
      ↓
Security Requirements
      ↓
Data Model
      ↓
System Behavior
      ↓
Implementation
      ↓
Observability
      ↓
Investigation
```

For example, "registration" is not simply:

```text
POST /register
```

It is a business and security workflow involving:

```text
Identity
+
Credentials
+
Abuse Prevention
+
Database Integrity
+
Security Evidence
+
Account State
+
Auditability
```

Likewise, "payment" is not simply:

```text
POST /payment
```

It is a workflow involving:

```text
Customer
+
Balance
+
Ledger
+
Payment State
+
Provider
+
Settlement
+
Beneficiary
+
Reconciliation
+
Audit
```

This is the perspective the project is intended to develop.

---

# 32. Long-Term Product Direction

The project can begin with fintech because that is the domain being studied deeply.

The underlying architecture could eventually apply to other domains:

```text
Fintech
   ↓
E-commerce
   ↓
Healthcare
   ↓
Logistics
   ↓
Other Operational Systems
```

The broader abstraction is:

> **AI-assisted investigation of complex business operations using controlled tools and trustworthy system evidence.**

Each industry would provide its own:

* Business vocabulary
* Rules
* Workflows
* Integrations
* Evidence
* Failure modes

---

# 33. Core Lesson

The project is deliberately teaching a different engineering mindset.

The objective is not merely:

> "Can I make the code work?"

The objective is:

> "Can I design a system that is secure, explainable, auditable, operationally useful, and aligned with the business problem?"

Every major technical decision should connect:

```text
Technical Correctness
        +
Security
        +
Business Correctness
        +
Operational Usefulness
        +
Future Investigation
```

The eventual investigation agent is built on top of this foundation.

The important achievement is therefore not simply building an agent.

It is learning how to build the **system that makes an agent useful, safe, explainable and operationally valuable**.
