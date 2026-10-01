# AI Fintech Operations Lab --- VS Code / Codex Handoff

> **Purpose of this file:** Transfer the important context from the
> long-running ChatGPT conversation into the repository so Codex/ChatGPT
> inside VS Code can continue the project without starting from zero.
>
> **Critical rule:** The **repository is the source of truth**. This
> document contains project history, intentions, architectural
> decisions, and previously discussed implementation state. Before
> changing code, inspect the repository and reconcile this document with
> what actually exists.

------------------------------------------------------------------------

## 1. How the AI coding assistant should work with me

I am building this project to learn, not merely to generate a finished
application.

When working on this repository:

1.  Inspect the relevant existing files before proposing changes.
2.  Explain the architecture and reasoning before making substantial
    changes.
3.  Do not blindly generate large amounts of code.
4.  Prefer small, understandable implementation steps.
5.  Explain important backend, database, security, concurrency, fintech,
    and agent concepts as they appear.
6.  Preserve the existing architecture unless there is a clear reason to
    change it.
7.  Clearly distinguish:
    -   what already exists,
    -   what is broken/incomplete,
    -   what is being implemented now,
    -   what is only planned.
8.  Run relevant tests after implementation when possible.
9.  Do not treat the LLM as a security boundary.
10. For financial operations, deterministic application rules remain
    authoritative.
11. Never invent repository state. Inspect it.
12. If this document conflicts with the current code, tell me and use
    the repository as the source of truth.

A useful interaction pattern is:

``` text
Inspect -> Explain -> Propose -> Implement -> Test -> Explain result
```

------------------------------------------------------------------------

# 2. Project

Project/repository:

``` text
ai_fintech_operation_lab
```

The project is an **AI Fintech Operations Lab**.

The objective is not simply:

> Build a chatbot.

The objective is to understand and demonstrate how a realistic fintech
backend works and then build an **AI-assisted operational investigation
system** on top of trustworthy financial evidence.

The project combines:

-   backend engineering,
-   authentication and authorization,
-   database design,
-   transaction management,
-   concurrency,
-   security,
-   auditability,
-   fintech business workflows,
-   payment operations,
-   operational investigation,
-   background workers,
-   failure/retry handling,
-   and AI agent workflows.

It is both:

1.  a learning environment, and
2.  proof-of-work for AI product / agent engineering in fintech.

------------------------------------------------------------------------

# 3. Central business problem

A representative customer complaint is:

> "I sent ₦2 million. My account was debited, but my beneficiary hasn't
> received the money."

A useful fintech investigation cannot answer this from a single
transaction row.

It may need evidence from:

-   Customer
-   Account
-   Beneficiary
-   Transaction
-   Ledger
-   Provider transaction
-   Provider response
-   Transaction events
-   Webhook
-   Settlement
-   Reconciliation
-   Reversal/refund
-   Security events
-   Audit history

The agent should gather evidence using controlled tools, reason over
that evidence, and stop when it has enough information or when it must
escalate.

------------------------------------------------------------------------

# 4. Core architectural principle

The project follows:

``` text
FINTECH SYSTEM + TRUSTWORTHY EVIDENCE
                ↓
        CONTROLLED DOMAIN TOOLS
                ↓
          INVESTIGATION AGENT
                ↓
      EVIDENCE-BACKED FINDING
                ↓
 EXPLANATION / ESCALATION / GATED ACTION
```

The AI should not be the system of record.

The application/database remains authoritative.

------------------------------------------------------------------------

# 5. Deterministic system vs AI responsibility

## Deterministic application responsibilities

The normal application layer should enforce:

-   authentication,
-   authorization,
-   input validation,
-   rate limiting,
-   database constraints,
-   transaction integrity,
-   idempotency,
-   business rules,
-   permissions,
-   approvals,
-   session management,
-   security controls,
-   audit logging,
-   financial state transitions.

These must not depend on the LLM behaving correctly.

## AI responsibilities

The AI layer is useful for:

-   deciding which investigation tool to call,
-   interpreting evidence,
-   correlating information across systems,
-   identifying inconsistencies,
-   explaining findings,
-   determining whether more evidence is needed,
-   deciding when the investigation cannot safely conclude,
-   recommending escalation,
-   summarizing operational evidence.

The LLM is **not a security boundary**.

------------------------------------------------------------------------

# 6. Agent design direction

An earlier prototype behaved roughly like:

``` text
customer message
      ↓
classifier
      ↓
payment agent
      ↓
transaction lookup
      ↓
LLM response
```

That was intentionally challenged because simply passing data from one
LLM step to another does not create a meaningful agentic workflow.

The desired design is closer to:

``` text
Customer complaint
        ↓
Intent / workflow selection
        ↓
Investigation agent
        ↓
  ┌──────────────────────────┐
  │ Controlled fintech tools │
  ├──────────────────────────┤
  │ get_customer             │
  │ get_accounts             │
  │ get_transaction          │
  │ get_ledger_entries       │
  │ get_provider_transfer    │
  │ get_transaction_events   │
  │ get_webhook_events       │
  │ get_reversal             │
  │ get_settlement           │
  │ get_reconciliation       │
  │ get_security_events      │
  │ get_audit_history        │
  └──────────────────────────┘
        ↓
Agent evaluates evidence
        ↓
Enough evidence?
   ↙              ↘
 no                yes
 ↓                  ↓
call another       produce evidence-
tool               backed finding
        ↓
possible escalation / gated action
```

The exact tool names above are conceptual. Inspect the repository before
assuming they exist.

------------------------------------------------------------------------

# 7. Agent loop principle

The agent should be able to:

1.  receive a customer/problem context,
2.  decide what information is missing,
3.  select an allowed domain tool,
4.  call the tool,
5.  inspect the result,
6.  update its understanding,
7.  decide whether another tool is required,
8.  stop when enough evidence exists,
9.  return a structured finding.

Conceptually:

``` python
while not enough_evidence:
    tool = agent.choose_tool(current_evidence)
    result = execute_allowed_tool(tool)
    evidence.append(result)

return build_investigation_result(evidence)
```

The agent should **not** receive arbitrary SQL access.

Tools should expose controlled business/domain operations.

------------------------------------------------------------------------

# 8. Evidence-first rule

A critical design rule from the project:

> The application result and authoritative financial records are the
> source of truth. The response layer must not invent facts.

The AI must not invent:

-   transaction IDs,
-   statuses,
-   provider responses,
-   URLs,
-   actions,
-   policies,
-   refunds,
-   reversals,
-   settlement outcomes,
-   UI features,
-   account balances,
-   or unsupported conclusions.

A finding should be traceable back to evidence returned by tools.

------------------------------------------------------------------------

# 9. Investigation outcomes

The system should be comfortable returning:

``` text
CONFIRMED
```

when evidence supports a conclusion,

or:

``` text
UNKNOWN / INSUFFICIENT EVIDENCE
```

when it does not.

The AI should not force a conclusion.

Example:

``` text
Transaction status: completed
Provider status: completed
Beneficiary receipt: unknown

Finding:
The provider reports the transfer as completed, but the available
evidence does not independently confirm beneficiary receipt.

Next step:
Escalate or obtain downstream/beneficiary-bank evidence.
```

This is preferable to inventing that the beneficiary received the money.

------------------------------------------------------------------------

# 10. Important payment investigation scenarios

The lab should eventually support realistic cases such as:

-   successful transaction but beneficiary says funds were not received,
-   account debited but provider transaction failed,
-   pending/delayed transfer,
-   failed transaction without reversal,
-   wrong transfer,
-   duplicate transaction,
-   fee discrepancy,
-   FX discrepancy,
-   incorrect account credit,
-   provider says completed but internal state disagrees,
-   webhook/provider state mismatch,
-   reconciliation mismatch.

Do not implement all of these at once.

The preferred approach is to make one investigation workflow serious and
realistic before expanding.

------------------------------------------------------------------------

# 11. Historical prototype evidence

Earlier prototype work included structured investigation results such
as:

``` text
payment_found
transaction_id
status
finding
evidence
next_step
```

One historical mock example was similar to:

``` text
Transaction: TXN-100001
Amount: ₦1,500,000
status: processing
debit_status: debited
provider_status: accepted
beneficiary_status: not_credited
```

Another early demo discussed records like:

``` text
TXN_001:
internal/provider completed,
but beneficiary receipt remained unknown.

TXN_002:
provider failed,
customer debit existed,
and reversal evidence was missing.
```

These are historical examples and **must not be assumed to exist in the
current repository**.

------------------------------------------------------------------------

# 12. Backend technology direction

Technologies discussed/used for the project include:

-   Python 3.12
-   FastAPI
-   PostgreSQL
-   SQLAlchemy
-   Alembic
-   Redis
-   Docker Compose
-   Pydantic
-   background worker patterns

PostgreSQL/pgvector was also discussed as part of the broader project
direction.

Again, inspect `pyproject.toml`, Docker files, environment
configuration, and imports to determine the exact current stack.

------------------------------------------------------------------------

# 13. Docker architecture

The project has been developed using Docker Compose.

Conceptually:

``` text
Docker Compose network
│
├── API / FastAPI container
├── PostgreSQL container
└── Redis container
```

Inside a Compose network, services can communicate using Compose service
names as hostnames.

For example, if the Redis service is named:

``` yaml
redis:
```

then another Compose container normally connects using:

``` text
redis
```

rather than `localhost`.

Do not assume service names; inspect `compose.yaml` /
`docker-compose.yml`.

------------------------------------------------------------------------

# 14. Application layering

A preferred architecture discussed for the project is roughly:

``` text
route
  ↓
service / business logic
  ↓
database/model
```

Route handlers should remain relatively thin.

Business logic should not be scattered through HTTP route functions.

Where appropriate, separate:

-   schemas,
-   routes,
-   services,
-   models,
-   infrastructure,
-   workers,
-   security utilities.

Preserve the current repository conventions rather than forcing a new
folder structure.

------------------------------------------------------------------------

# 15. Authentication/security foundation

The project has been deliberately building the normal fintech backend
before giving an AI agent powerful access.

Previously discussed/implemented foundation includes some combination
of:

-   User model
-   registration
-   password hashing
-   registration attempts
-   database integrity protection
-   Redis-backed rate limiting
-   audit logging
-   verification tokens
-   user verification
-   session/authentication work

The historical sequence was approximately:

``` text
Register
   ↓
Verify
   ↓
Session / Login
   ↓
Transactions / fintech evidence
   ↓
Email/outbox
   ↓
Worker
   ↓
Agent investigation layer
```

The exact current completion state MUST be verified in the repository.

------------------------------------------------------------------------

# 16. Registration

A typical registration architecture discussed was:

``` text
POST /register
      ↓
Pydantic request validation
      ↓
registration service
      ↓
hash password
      ↓
create pending customer/user
      ↓
commit
      ↓
audit
      ↓
verification workflow
```

Security concerns explored around registration include:

-   registration spam,
-   rate limiting,
-   IP information,
-   database uniqueness/integrity,
-   auditability.

When handling client IPs behind infrastructure such as:

``` text
Cloudflare
   ↓
Nginx
   ↓
FastAPI
```

do not blindly trust arbitrary `X-Forwarded-For` headers.

Trusted proxy configuration determines which forwarded headers are
authoritative.

------------------------------------------------------------------------

# 17. User verification

The verification workflow was being designed around a state transition
similar to:

``` text
PENDING
   ↓
verification token validated
   ↓
ACTIVE
```

Associated behavior discussed included:

-   locate verification token,
-   validate it,
-   update user state,
-   write a `USER_VERIFIED` audit event,
-   invalidate/delete the used token.

Inspect the repository to see what is currently implemented.

------------------------------------------------------------------------

# 18. Auditability

Audit history is a core feature, not optional logging.

The project has discussed an `AuditLog` model/service and recording
events such as successful registration and verification.

Long-term, audit evidence should help answer:

``` text
Who did what?
When?
Against which resource?
What state changed?
Why?
What evidence existed?
Was the action performed by a user, system, worker, or AI-assisted workflow?
```

The agent should never silently perform important operations outside the
audit model.

------------------------------------------------------------------------

# 19. Sessions and authentication roadmap

Authentication work has included/planned concepts such as:

-   login,
-   sessions,
-   revocation,
-   login attempts,
-   security events,
-   authorization.

These should remain deterministic application responsibilities.

The AI agent should not decide whether authentication succeeds.

------------------------------------------------------------------------

# 20. Email / outbox architecture

The most recent work has moved into the email/outbox and worker area.

The project is learning a production-style pattern rather than sending
emails directly inside important request transactions.

Conceptually:

``` text
business operation
      ↓
database transaction
      ↓
EmailOutbox row created
      ↓
commit
      ↓
background worker
      ↓
claim pending email
      ↓
send email
      ↓
mark sent / failed / retry
```

This provides a foundation for learning:

-   asynchronous processing,
-   reliability,
-   retries,
-   concurrency,
-   locking,
-   failure recovery,
-   operational visibility.

------------------------------------------------------------------------

# 21. Current function: `claim_pending_email`

The recent implementation being worked on is:

``` python
def claim_pending_email(
    session: Session,
) -> EmailOutbox | None:

    stmt = (
        select(EmailOutbox)
        .where(EmailOutbox.status == "pending")
        .order_by(EmailOutbox.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    email = session.scalar(stmt)

    if email is None:
        return None

    email.status = "processing"
    email.attempts += 1

    session.commit()

    return email
```

Before using this exact code, inspect the repository because
names/imports/model fields may have changed.

------------------------------------------------------------------------

# 22. Why `claim_pending_email` matters

This is not just a query for the first email.

The important concurrency concept is:

``` text
SELECT ... FOR UPDATE SKIP LOCKED
```

Imagine:

``` text
Worker A
Worker B
Worker C
```

all asking for pending work.

Without safe claiming, two workers could select the same email and send
it twice.

The desired behavior is approximately:

``` text
Worker A locks Email #1
Worker B skips Email #1 and claims Email #2
Worker C skips both and claims Email #3
```

`SKIP LOCKED` helps workers avoid waiting on rows already claimed/locked
by another worker.

The transition:

``` text
pending -> processing
```

represents ownership/claiming of the job.

This area should be treated carefully because transaction boundaries
determine whether the locking strategy is actually safe.

------------------------------------------------------------------------

# 23. Current task

**This is the immediate continuation point.**

The task is to integrate `claim_pending_email` into the email worker
flow.

Before changing code:

1.  Find the `EmailOutbox` model.
2.  Find `claim_pending_email`.
3.  Find the DB/session setup.
4.  Find the current worker implementation, if one exists.
5.  Find email sending/provider code, if it exists.
6.  Find relevant tests.
7.  Trace the transaction lifecycle.
8.  Explain the existing flow.

Then propose how the worker should use the claim operation.

Do **not** assume file paths from old conversations.

------------------------------------------------------------------------

# 24. Desired worker lifecycle

Conceptually, the worker will eventually look like:

``` text
worker starts iteration
       ↓
open DB session
       ↓
claim_pending_email()
       ↓
email exists?
  ↙            ↘
no              yes
↓                ↓
wait/exit      send email
                 ↓
            success?
            ↙      ↘
          yes       no
           ↓         ↓
        mark sent   record failure
                    retry / dead-letter policy
```

The exact implementation should be driven by the repository and current
design.

------------------------------------------------------------------------

# 25. Worker reliability questions to think through

Do not rush past these issues:

### Claim atomicity

Does the transaction correctly guarantee that another worker cannot
claim the same job?

### Commit boundary

When should the claim be committed?

What happens to the lock after commit?

### Worker crash

What happens if:

``` text
pending -> processing
```

is committed and then the worker crashes before sending?

The system eventually needs a recovery strategy for stuck `processing`
jobs.

### Duplicate sending

Email delivery is an external side effect.

A database rollback cannot "unsend" an email.

Think about idempotency and retry semantics.

### Attempts

`attempts += 1` should have a defined meaning.

Does an attempt mean:

-   claimed,
-   send started,
-   provider request made,
-   or send failed?

Choose semantics deliberately.

### Failure state

Possible states may eventually include something like:

``` text
pending
processing
sent
failed
```

Potential retry/dead-letter behavior should be explicit.

Do not add states unless they fit the existing model.

------------------------------------------------------------------------

# 26. Testing expectations for the worker

When integrating the worker, tests should eventually cover important
behavior such as:

-   returns `None` when no pending email exists,
-   claims the oldest eligible pending email,
-   changes state correctly,
-   increments attempts correctly,
-   does not claim already-processing work,
-   handles send success,
-   handles send failure,
-   retry behavior,
-   concurrency/locking behavior where practical.

Use the existing test stack and conventions.

Do not invent a new test framework.

------------------------------------------------------------------------

# 27. Why email/outbox work belongs in the fintech lab

The email system is intentionally part of the learning path.

A serious financial system must understand reliable background work
before introducing autonomous/agentic actions.

The same ideas later apply to:

-   payment provider requests,
-   webhooks,
-   settlement jobs,
-   reconciliation,
-   notification delivery,
-   scheduled investigation jobs,
-   agent-triggered operational tasks.

Concepts being learned here include:

``` text
transaction boundaries
locking
idempotency
outbox
workers
retries
failure handling
auditability
```

These become important when AI workflows begin interacting with
operational systems.

------------------------------------------------------------------------

# 28. Fintech evidence models --- future direction

After the security/application foundation is stable, the project should
develop realistic fintech evidence.

Conceptual domain entities include:

``` text
Customer
Account
Beneficiary
Transaction
LedgerEntry
ProviderTransaction
TransactionEvent
WebhookEvent
Settlement
Reconciliation
Reversal
SecurityEvent
AuditLog
```

Do not create all of these simply because they appear here.

Each should be introduced because a real workflow needs it.

------------------------------------------------------------------------

# 29. Example investigation

Customer:

``` text
I sent ₦2 million but my beneficiary hasn't received the money.
```

A realistic agent should not immediately answer.

It may reason:

``` text
I need to identify the customer/account and transfer.
```

Then:

``` text
get_customer(...)
get_transactions(...)
```

It discovers the transaction and sees:

``` text
internal_status = completed
```

That alone is not enough.

It may request:

``` text
get_provider_transfer(transaction_id)
```

Suppose provider evidence says:

``` text
provider_status = completed
```

Still, beneficiary receipt may not be independently known.

It may inspect:

``` text
get_transaction_events(...)
get_webhook_events(...)
get_ledger_entries(...)
get_reconciliation(...)
```

Eventually it may conclude:

``` text
Internal debit: confirmed
Internal transaction: completed
Provider: completed
Beneficiary receipt: not independently confirmed
Reversal: none
```

Then return an evidence-backed explanation and appropriate escalation.

That is the type of agent workflow this project is trying to build.

------------------------------------------------------------------------

# 30. Read-only agent first

The first serious version of the fintech agent should primarily
investigate.

Prefer:

``` text
READ
REASON
EXPLAIN
ESCALATE
```

before:

``` text
MOVE MONEY
REFUND
REVERSE
CHANGE ACCOUNT STATE
```

High-impact actions should later require:

-   deterministic validation,
-   authorization,
-   policy checks,
-   explicit permissions,
-   possibly human approval,
-   audit logging,
-   idempotency.

------------------------------------------------------------------------

# 31. Tool design

Agent tools should expose business capabilities, not database internals.

Prefer conceptual interfaces like:

``` python
get_transaction(transaction_id)
get_provider_transfer(transaction_id)
get_ledger_entries(transaction_id)
get_reversal(transaction_id)
```

rather than:

``` python
run_sql("SELECT ...")
```

Benefits:

-   smaller attack surface,
-   predictable schemas,
-   authorization can be enforced,
-   easier testing,
-   easier auditing,
-   easier observability,
-   reduced hallucination opportunity.

------------------------------------------------------------------------

# 32. Agent permissions

Eventually tools should have explicit permissions.

Conceptually:

``` text
read_customer
read_transaction
read_ledger
read_provider_status
read_audit_history
```

and later, separately:

``` text
request_refund
request_reversal
freeze_account
```

Read and write capabilities should not be casually mixed.

------------------------------------------------------------------------

# 33. Human escalation

The system must support:

``` text
I do not have enough evidence to safely conclude this investigation.
```

Possible escalation reasons:

-   conflicting records,
-   provider unavailable,
-   missing webhook,
-   reconciliation incomplete,
-   beneficiary receipt cannot be confirmed,
-   action exceeds agent permissions,
-   suspicious/security-sensitive activity,
-   manual operations review required.

Escalation is part of correct agent behavior.

------------------------------------------------------------------------

# 34. Security principle for agentic systems

A major principle of this project:

> AI reasoning may decide what to investigate, but deterministic systems
> decide what is allowed.

For example:

``` text
LLM:
"I should inspect provider status."

Application:
"Allowed: read_provider_status."
```

versus:

``` text
LLM:
"I should refund the customer."

Application:
"Denied unless deterministic authorization, policy, state,
idempotency and approval requirements are satisfied."
```

------------------------------------------------------------------------

# 35. Broader learning roadmap

The project is intended to progressively cover:

``` text
FastAPI/backend fundamentals
        ↓
PostgreSQL + SQLAlchemy
        ↓
database transactions
        ↓
authentication
        ↓
authorization
        ↓
Redis
        ↓
rate limiting
        ↓
sessions
        ↓
audit logs
        ↓
outbox
        ↓
workers
        ↓
locking/concurrency
        ↓
retries/idempotency
        ↓
fintech transaction models
        ↓
provider integrations
        ↓
webhooks
        ↓
ledger
        ↓
settlement
        ↓
reconciliation
        ↓
controlled AI tools
        ↓
agent loop
        ↓
human escalation
        ↓
gated actions
        ↓
agent observability/audit
```

This roadmap is directional, not a command to implement everything now.

------------------------------------------------------------------------

# 36. Development philosophy

Do not optimize for:

> How quickly can AI write the application?

Optimize for:

> Can I explain why the system works, what can fail, and how we know it
> is correct?

Important questions throughout the project:

-   What business problem does this component solve?
-   What invariant are we protecting?
-   What happens when two requests happen simultaneously?
-   What happens when the process crashes?
-   What happens when an external provider times out?
-   Can an operation safely be retried?
-   What evidence would operations need to investigate this?
-   What should be audited?
-   What should the AI be allowed to see?
-   What should the AI be allowed to do?
-   What must remain deterministic?

------------------------------------------------------------------------

# 37. What NOT to do

Do not:

-   rebuild the repository from scratch,
-   introduce a new architecture without inspecting the old one,
-   assume every planned model already exists,
-   generate arbitrary financial actions,
-   give the agent unrestricted SQL,
-   hide business logic in prompts,
-   use the LLM to enforce authorization,
-   skip transaction/concurrency reasoning,
-   mark something "production ready" without evidence,
-   silently change schema without appropriate migration,
-   add dependencies unnecessarily,
-   over-engineer before the current workflow works.

------------------------------------------------------------------------

# 38. Repository discovery checklist for Codex

At the beginning of a new session, inspect:

``` text
README*
AGENTS.md
pyproject.toml
compose.yaml / docker-compose.yml
.env.example
alembic.ini
alembic/
app/
tests/
```

Then locate:

``` text
database/session configuration
models
schemas
routes
services
Redis configuration
auth/security code
audit service/model
verification workflow
EmailOutbox
email services
claim_pending_email
worker code
tests
```

Report the actual architecture before making major edits.

------------------------------------------------------------------------

# 39. Immediate Codex prompt

After reading this file, start with:

``` text
Read this handoff document and inspect the current repository.

The repository is the source of truth.

Our immediate task is to continue the email outbox worker work around
claim_pending_email.

Before changing code:

1. locate EmailOutbox and claim_pending_email;
2. locate the DB session lifecycle;
3. locate the worker/email sending implementation;
4. locate relevant tests;
5. trace the current transaction lifecycle;
6. tell me what from this handoff is already implemented, partially
   implemented, missing, or different in the repository.

Then explain the smallest correct next implementation step.

Do not modify code until you have explained the current architecture
and proposed the next step.
```

------------------------------------------------------------------------

# 40. Current continuation point

The current focus is **not yet to jump ahead to the final fintech
agent**.

Continue from:

``` text
Email outbox
    ↓
claim_pending_email
    ↓
worker integration
    ↓
send/failure/retry semantics
    ↓
tests
```

Once that foundation is understood and working, continue through the
backend/fintech architecture toward the controlled investigation-agent
workflow.

------------------------------------------------------------------------

# 41. Final instruction to future AI sessions

This file is context, not authority over the code.

Always use:

``` text
repository state
      +
tests
      +
database behavior
      +
explicit architectural decisions
```

as the source of truth.

If something in this document is outdated, say:

``` text
"The handoff says X, but the repository currently implements Y."
```

Then explain the difference and continue from the real repository state.

The goal is to build a system I understand deeply enough to reason about
as a backend engineer, fintech engineer, and AI product/agent engineer.
