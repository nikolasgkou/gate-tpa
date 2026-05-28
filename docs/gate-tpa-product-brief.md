# Gate TPA Product Brief

## Product Intent

Gate TPA is a trusted personal assistant that sits between an inbound caller and the person being called. Users forward calls to Gate TPA, and the service decides whether to block, connect, reroute, or handle the call through an AI agent.

The product should feel like a personal gatekeeper, not a generic spam blocker. Its core promise is: important people still get through, malicious or unwanted callers do not, and ambiguous callers are handled without wasting the user's attention.

## Working Assumptions

- The first user workflow is inbound call forwarding from a user's phone number to Gate TPA.
- Caller ID is useful but not fully trustworthy; decisions should include confidence and fallback handling.
- The user remains in control through explicit allowlists, blocklists, and routing rules.
- The AI agent is a premium or advanced layer, not required for the first usable version.
- The product must avoid making irreversible decisions when confidence is low, especially for unknown callers.

## Decision Layers

### Layer 1: Public Risk Check

Purpose: identify callers already known or suspected to be malicious.

Inputs:
- Caller ID / phone number.
- Public, commercial, or crowdsourced phone reputation data.
- Internal aggregate reports once the product has enough usage.

Possible outputs:
- Known malicious: drop, voicemail, or AI containment.
- Suspicious: continue to user rules with elevated risk.
- Unknown or clean: continue to user rules.

Product note: this layer should be framed as evidence, not truth. False positives are expensive.

### Layer 2: User Policy

Purpose: apply the user's explicit preferences.

Inputs:
- Allowlist.
- Blocklist.
- Contact groups.
- Per-contact routing rules.
- Time-based rules.
- Status rules, such as in meeting, sleeping, focus mode, or vacation.

Possible outputs:
- Connect directly to the user.
- Drop or reject.
- Send to voicemail or transcript capture.
- Reroute to another person.
- Route to the AI agent.

Product note: this is the trust anchor. If a user says a caller always gets through, the product should honor that unless there is a high-confidence safety override that the user explicitly enabled.

### Layer 3: AI Agent

Purpose: resolve ambiguous or context-sensitive calls by speaking with the caller and deciding what should happen next.

Capabilities:
- Ask who is calling and why.
- Determine urgency.
- Check context such as calendar availability.
- Interrupt the user only when appropriate.
- Take notes and send a summary.
- Ask the caller to try again later.
- Escalate to a delegate or alternate contact.
- Apply user-specific instructions.

Product note: the AI should act from policy, not vibes. It needs explicit decision thresholds and should explain its handoff reason to the user.

## Core Call Outcomes

- Block: known unwanted or malicious caller.
- Direct connect: trusted caller or allowed contact.
- Screen: AI agent asks for identity, reason, and urgency.
- Take message: caller leaves structured information.
- Reroute: call goes to a delegate, team member, or alternate number.
- Defer: caller is asked to call later or wait for follow-up.
- Interrupt: user is contacted during protected time because the caller and reason meet the user's threshold.

## MVP

The narrow first product should prove that call forwarding plus rule-based screening is valuable before building the full AI layer.

MVP scope:
- User can configure call forwarding to Gate TPA.
- Gate receives inbound call events.
- Gate performs a caller reputation lookup.
- Gate applies allowlist and blocklist rules.
- Gate can directly connect, block, or send to a simple screening flow.
- Gate produces a call log with outcome and reason.
- User can review and correct decisions after the call.

Intentionally out of scope for MVP:
- Deep calendar integration.
- Multi-person delegation workflows.
- Fully autonomous interruption decisions.
- Complex enterprise policy management.
- Broad third-party integrations.

## First AI Slice

The first AI agent should be a constrained call screener:

- Greets the caller.
- Asks for name, organization, reason, and urgency.
- Classifies the call as spam, routine, urgent, or trusted-but-unknown.
- Summarizes the call for the user.
- Follows a small set of deterministic routing policies.

This keeps the assistant useful while avoiding an opaque autonomous agent too early.

## User Experience Principles

- The user should understand why a call was handled a certain way.
- The caller should experience a short, professional interaction.
- High-confidence decisions should be fast.
- Low-confidence decisions should preserve optionality.
- The product should minimize setup: start with contacts, allowlist, blocklist, and a few availability modes.
- Every automated decision should improve the user's future control through review actions like always allow, always block, or ask me next time.

## Trust And Safety Risks

- Caller ID spoofing can defeat naive caller-based rules.
- False positive blocking can cause serious missed calls.
- AI conversations may collect sensitive personal information.
- Recording and transcription laws vary by jurisdiction.
- Calendar integration exposes sensitive availability and meeting details.
- Scammers may attempt prompt injection or social engineering through the voice agent.

Mitigations:
- Treat caller reputation as probabilistic.
- Make user-defined allow rules explicit and visible.
- Keep early AI policies narrow and auditable.
- Store call summaries with clear retention controls.
- Avoid exposing calendar details to callers.
- Require user consent for recording, transcription, and integrations.

## Open Product Questions

- Is Gate TPA primarily for consumers, solo professionals, executives, families, or small businesses?
- Should the default unknown-caller experience be voicemail-like, receptionist-like, or security-check-like?
- What is the user's tolerance for missed calls versus unwanted interruptions?
- Should emergency interruption be allowed for non-allowlisted callers?
- Which telephony provider should be used first?
- Does the product need to support outbound callbacks from the assistant?
- What data sources are acceptable for public/crowdsourced caller reputation?

## Suggested Next Slice

Define the call decision engine before choosing UI or AI architecture.

Success criteria:
- Given caller risk, user policy, and availability context, the engine returns one explicit outcome.
- The outcome includes a human-readable reason.
- Unknown callers default to screening, not blocking.
- User allowlist and blocklist behavior is deterministic.
- The model is testable without telephony infrastructure.

Candidate decision shape:

```text
Incoming call
-> normalize caller identity
-> fetch public risk signals
-> load user policy
-> evaluate deterministic rules
-> route to direct connect, block, reroute, message, or AI screen
-> log outcome and reason
```
