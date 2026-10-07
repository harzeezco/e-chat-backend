```md
# Research Note: Where Agentic Reasoning May Extend Deterministic Security

## Overview

Traditional application security relies heavily on deterministic controls such as:

- Authentication
- Authorization
- Session validation
- Rate limiting
- Input validation
- Role-based access control
- Database constraints
- Policy enforcement

These controls are necessary because they create clear and enforceable security boundaries.

However, many real-world security incidents do not happen because authentication or authorization logic is completely missing.

They can happen when an attacker successfully operates inside valid application flows.

This creates a different security question.

Traditional security asks:

```text
Is this request allowed?
```

Behaviour-oriented security asks:

```text
Does this sequence of behaviour make sense?
```

This research explores where agentic systems may complement deterministic controls by investigating sequences, context, historical behaviour, relationships between events, and weak signals that may be difficult to capture with isolated rules.

---

# 1. Account Takeover After Successful Authentication

One important scenario is account takeover where an attacker successfully passes authentication.

The session may contain:

```text
correct password
valid OTP
valid cookie
valid JWT
valid refresh token
```

From the authentication system's perspective, the session may appear valid.

The interesting security problem begins after authentication.

Consider the following sequence:

```text
new device
+
new geographic pattern
+
password reset
+
new beneficiary
+
unusually large transfer
```

Each action may individually be legitimate.

The security concern emerges from the relationship between the actions.

A deterministic backend usually evaluates each request independently:

```text
Is the JWT valid?
Is the user authorized?
Is the transfer amount within the allowed limit?
```

An investigation-oriented system could instead reconstruct the wider session timeline and evaluate whether the sequence resembles normal behaviour or a possible account takeover.

The research question becomes:

> How can an application continuously evaluate behaviour after authentication without replacing deterministic authorization controls?

---

# 2. Credential Sharing and Stolen Sessions

Another relevant case involves session reuse or stolen credentials.

For example:

```text
Session A
Nigeria
Chrome / Windows
```

Ten minutes later:

```text
Same account

Session B
Different device
Different behavioural pattern
```

Neither session necessarily proves malicious activity.

However, the surrounding event sequence may provide additional evidence:

```text
failed MFA attempts
→ successful login
→ API keys viewed
→ beneficiary changed
→ payout requested
```

Traditional rule-based systems can detect many of these patterns.

The challenge is that the number of possible combinations grows quickly.

A single event may carry little meaning, while several events observed together may significantly change the interpretation.

This suggests a potential role for agentic investigation:

```text
individual events
        ↓
historical context
        ↓
session relationships
        ↓
behavioural sequence
        ↓
evidence-based hypothesis
```

The important distinction is that the agent does not replace session validation.

It investigates what happens after the session has already been accepted as valid.

---

# 3. Slow and Distributed Attacks

Rate limiting works particularly well when suspicious behaviour happens within a clear time window.

For example:

```text
100 login attempts / minute
```

A deterministic rate limiter can easily respond.

A more difficult pattern might look like:

```text
3 attempts today
4 attempts tomorrow
2 attempts next week

different IP addresses
same collection of accounts
```

Each individual event may appear harmless.

The security concern only becomes visible when events are correlated across a longer period.

Possible examples include:

- slow credential stuffing
- account enumeration
- distributed probing
- repeated recovery attempts
- low-frequency abuse across multiple identities

This creates another research area:

> Can an agent investigate long-lived behavioural patterns that would otherwise require a large collection of manually maintained correlation rules?

The purpose would not be to replace rate limiting.

Instead:

```text
Rate limiter
→ blocks obvious high-frequency abuse

Behavioural investigation
→ searches for slower cross-event patterns
```

---

# 4. Insider Misuse

Authorization systems are designed to answer whether a user has permission to access a resource.

For example:

```text
role = support
permission = view_customer
```

Therefore:

```text
GET /customers/123
```

may be completely authorized.

However, authorization alone does not explain why the employee is accessing the resource.

Consider:

```text
view customer A
view customer B
view customer C
view customer D
...
200 customer profiles in 30 minutes
```

Every request might satisfy RBAC.

The behavioural question is different:

> Is this pattern consistent with the employee's operational responsibilities?

Additional context might include:

```text
assigned support cases
department
normal access volume
customer sensitivity
time of access
relationship between accessed accounts
previous behaviour
```

This illustrates an important limitation of pure authorization:

```text
Authorization:
Can this employee access customer records?

Behavioural investigation:
Does this pattern of authorized access make sense?
```

For high-trust systems such as fintech platforms, this distinction may be particularly important.

---

# 5. Business-Logic Abuse

Some security incidents do not require bypassing authentication or exploiting traditional vulnerabilities.

Instead, legitimate product workflows may be combined in unintended ways.

Example:

```text
create account
↓
verify account
↓
fund wallet
↓
create beneficiary
↓
initiate transfer
↓
cancel
↓
retry
↓
repeat under specific timing conditions
```

Every endpoint may behave according to its specification.

The weakness may exist in the interaction between several valid operations.

This can appear in areas such as:

- payment retries
- duplicate requests
- reversals
- refunds
- promotional systems
- withdrawal workflows
- beneficiary creation
- state transitions
- race conditions
- transaction limits

This suggests that application security should not only examine isolated endpoints.

It may also need to reason about:

```text
workflow composition
+
state transitions
+
event ordering
+
historical behaviour
```

Agentic reasoning may be useful here because the investigation unit becomes the entire workflow rather than a single request.

---

# Request Security vs Behavioural Security

The distinction can be represented as two related layers.

```text
REQUEST SECURITY

authentication
authorization
validation
rate limits
permissions
cryptographic checks
session policies

        │
        ▼

BEHAVIOURAL SECURITY

event sequences
context
history
relationships
behavioural changes
cross-session patterns
hypotheses
anomalies
```

The first layer remains deterministic.

The second layer attempts to interpret what the allowed activity means in context.

These systems should not be treated as alternatives.

A more useful model is:

```text
Deterministic security
+
behavioural investigation
```

---

# Avoiding the "Anomaly Detector" Trap

A weak architecture would be:

```text
application logs
      ↓
LLM
      ↓
"suspicious"
```

This provides little explanation and may produce unreliable conclusions.

A stronger architecture treats security monitoring as an investigation problem.

```text
Security event
      ↓
Retrieve account and session context
      ↓
Build activity timeline
      ↓
Evaluate deterministic security signals
      ↓
Form hypotheses
      ↓
Retrieve relevant evidence
      ↓
Compare with historical behaviour
      ↓
Identify supporting and conflicting evidence
      ↓
Determine missing evidence
      ↓
Produce risk assessment
      ↓
Recommend next action
```

This closely resembles evidence-driven investigations in other operational domains.

---

# Example Investigation

## Hypothesis

```text
Possible account takeover
```

## Evidence Supporting the Hypothesis

```text
- Login originated from a previously unseen device
- Password changed shortly after login
- New beneficiary created four minutes later
- Transfer amount is significantly higher than historical transfers
- Session originated from an unusual network
```

## Evidence Against the Hypothesis

```text
- MFA was successfully completed
- Login occurred within the customer's usual country
```

## Missing Evidence

```text
- Device reputation
- History of the beneficiary relationship
- Recent account recovery activity
- Previous sessions from the same network
```

## Possible Recommendation

```text
Require step-up authentication before completing the high-risk action.
```

The important difference is that the system does not simply produce:

```text
Fraud probability: 87%
```

Instead, it produces an evidence-backed investigation:

```text
Hypothesis
+
supporting evidence
+
contradicting evidence
+
missing evidence
+
recommended response
```

---

# Proposed Security Architecture

```text
User Action
    ↓
Deterministic Security Layer
    ↓
Authentication
Authorization
Session Validation
Rate Limiting
Business Rules
Policy Enforcement
    ↓
Application Action
    ↓
Security Events
    ↓
Investigation Layer
    ↓
Timeline Reconstruction
Context Retrieval
Evidence Collection
Hypothesis Formation
Behavioural Analysis
    ↓
Risk Assessment
    ↓
Recommendation
    ↓
Deterministic Enforcement or Human Review
```

A key design principle is:

> The reasoning system should not become the security boundary.

The agent may investigate and recommend.

The deterministic system should still control actions such as:

```text
session revocation
account lock
step-up authentication
transfer blocking
permission changes
financial limits
```

---

# Research Direction

The broader research question is not whether AI should replace authentication or authorization.

It is:

> How can agentic reasoning complement deterministic application security by continuously investigating authenticated behaviour?

This introduces a potentially useful distinction:

```text
Authentication establishes whether an identity can access the system.

Authorization establishes what that identity can do.

Behavioural investigation evaluates whether the sequence of allowed actions still appears trustworthy.
```

The interesting area therefore exists after successful authentication and authorization, where the system must interpret behaviour over time.

This may be especially relevant in fintech systems because financial applications combine:

- sensitive identity data
- privileged operations
- payment workflows
- account changes
- financial state transitions
- insider access
- fraud risk
- external providers
- asynchronous events

The emerging architecture is therefore not:

```text
AI replaces security rules
```

but rather:

```text
Deterministic controls
+
continuous event collection
+
contextual investigation
+
evidence-driven agent reasoning
+
deterministic enforcement
```

This provides a foundation for exploring security systems that are not only capable of rejecting invalid requests, but also capable of investigating suspicious behaviour occurring through otherwise valid application flows.
```