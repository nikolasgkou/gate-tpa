# Gate TPA

Gate TPA is a trusted personal assistant for phone calls. It protects vulnerable
or busy people by screening incoming SIP calls, playing short AI voice prompts,
and routing calls to the right trusted person.

The MVP runs on an Azure-hosted Asterisk PBX. Linphone clients register as SIP
extensions, Asterisk applies the scenario routing, and Gemini provides the Gate
AI voice for prompts and live executive call screening.

## Demo Extensions

| Extension | Persona | Role |
| --- | --- | --- |
| `1001` | Emma Newman | Child |
| `1002` | Sarah Newman | Mother |
| `1003` | Olivia Descarte | Elderly person |
| `1004` | Mark Descarte | Son and caregiver |
| `1005` | Bruce Jameson | Executive |
| `1006` | John Michaels | Employee |
| `1007` | Stranger | Unknown caller |
| `1008` | Gate AI Agent | Reserved AI identity |

## User Journey

### 1. Trusted Parent Calls Child

Sarah calls Emma:

```text
1002 -> 1001
```

Gate recognizes Sarah's extension as trusted, plays:

```text
Hi Sarah. Connecting you to Emma.
```

Asterisk then forwards the call to Emma. Emma answers:

```text
Hi mommy!
```

This shows that trusted callers can reach the protected person with only a short
Gate announcement.

### 2. Stranger Calls Child

The stranger attempts to call Emma:

```text
1007 -> 1001
```

Gate does not let the stranger reach Emma directly. It plays:

```text
This call will be routed to Sarah Newman.
```

Asterisk then forwards the call to Sarah:

```text
1007 -> Gate -> 1002
```

This shows child protection: unknown callers can attempt the call, but Gate
intercepts and routes them to the parent.

### 3. Stranger Calls Elderly Person

The stranger attempts to call Olivia:

```text
1007 -> 1003
```

Gate protects Olivia and plays:

```text
Olivia cannot take this call directly. Would you like to leave a message or speak with her caregiver?
```

For the MVP demo, Gate then plays:

```text
I will connect you with her caregiver.
```

Asterisk forwards the call to Mark:

```text
1007 -> Gate -> 1004
```

This shows vulnerable-person protection: unknown callers are routed to the
caregiver instead of directly reaching Olivia.

### 4. Employee Calls Executive During Meeting

John calls Bruce:

```text
1006 -> 1005
```

Gate answers live through Gemini:

```text
Bruce is in a meeting. What is this regarding?
```

If John does not say the call is urgent, Gate responds:

```text
Thanks. Bruce is in a meeting and will be notified about this call after the meeting.
```

The call ends and Bruce is not interrupted.

If John says the call is urgent, Gate responds:

```text
Understood. I'll try Bruce now. Please hold.
```

Asterisk forwards the call to Bruce:

```text
1006 -> Gate -> 1005
```

Bruce answers:

```text
We're in a meeting. Be quick.
```

This shows executive screening: Gate blocks routine calls and lets urgent calls
through.

## How It Works

Gate TPA has two routing modes.

The child and elderly-person scenarios use pre-rendered Gemini voice prompts
stored as Asterisk sound files. Asterisk plays the prompt with `Playback()` and
then continues with a normal SIP `Dial()`. This keeps the demo handoffs reliable:

```text
incoming SIP call -> Asterisk dialplan -> Gate prompt -> trusted extension
```

The executive scenario uses the live Gemini bridge. Asterisk answers the call
and streams phone audio to the local AudioSocket bridge. The bridge connects to
Gemini Live, listens for the caller's response, writes the screening outcome,
and Asterisk either transfers the call or ends it:

```text
incoming SIP call -> Asterisk AudioSocket -> Gemini Live -> outcome -> transfer or hangup
```

Routing is based on SIP extension numbers, not display names:

- Emma `1001` is directly reachable only from Sarah `1002`.
- Other callers to Emma are routed to Sarah.
- Olivia `1003` is directly reachable only from Mark `1004`.
- Other callers to Olivia are routed to Mark.
- Bruce `1005` is screened when John `1006` calls.

## Repository Layout

- `src/`: Gate AI service and Gemini AudioSocket bridge.
- `infra/`: Azure/Asterisk infrastructure and PBX configuration.
- `infra/asterisk/sounds/en/gate/`: pre-rendered Gate voice prompts.
- `bin/`: helper scripts.
- `docs/`: project documentation.

## Status

This is an MVP built for a short hackathon presentation. SIP accounts use simple
extension-based credentials and the PBX is intentionally configured for demo
speed rather than production hardening.
