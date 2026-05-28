# Gate TPA PBX Infrastructure

This deploys the MVP SIP target: an Azure-hosted Asterisk PBX for Linphone clients.

## Resources

- Ubuntu VM running Asterisk.
- Static public IP with DNS label.
- Network security group allowing:
  - `22/TCP` for SSH.
  - `80/TCP` for Let's Encrypt HTTP validation.
  - `443/TCP` for the Gate AI Agent webhook.
  - `5060/UDP` for SIP.
  - `10000-10100/UDP` for RTP media.

## Gate Voice Prompts

The simple demo handoff prompts are pre-rendered Gemini voice files under `infra/asterisk/sounds/en/gate`.
Install them on the PBX before applying the dialplan:

```sh
bin/install-asterisk-prompts.sh
```

The installer copies them into Asterisk's active data directory, `/usr/share/asterisk/sounds/en/gate`. The Emma and Olivia routes use Asterisk `Playback()` for these short prompts, then continue with normal `Dial()` forwarding. This keeps the scenario handoffs deterministic during the demo.

## Gemini AI Bridge

Route `9001` answers the call in Asterisk and streams audio to the local Gemini bridge:

```text
AudioSocket(00000000-0000-0000-0000-000000000001,127.0.0.1:9092)
```

The Gemini Live API is WebSocket-based, not SIP-based. The bridge process listens on `127.0.0.1:9092`, receives Asterisk AudioSocket PCM, streams caller audio to Gemini Live, and plays Gemini audio back into the call. The live bridge is used for `9001` and for the Bruce urgent/non-urgent screening route.

## Linphone Test Accounts

The MVP extensions use their extension number as the password. Retrieve the current VM copy after deployment:

```sh
az vm run-command invoke \
  --resource-group gate-tpa-mvp \
  --name gate-tpa-pbx \
  --command-id RunShellScript \
  --scripts 'cat /root/gate-tpa-linphone-credentials.txt' \
  --query "value[0].message" \
  --output tsv
```

Use these Linphone fields for any account:

- Username: one of `1001` through `1007`
- Auth username: same as username
- Password: same as username
- Domain/SIP server: deployment output `publicIpAddress` or `fqdn`
- Transport: `UDP`
- Port: `5060`
- Test call: dial `600` for echo test

Current contact mapping:

| Extension | Display name | Role |
| --- | --- | --- |
| `1001` | Emma Newman | child |
| `1002` | Sarah Newman | mother |
| `1003` | Olivia Descarte | Alzheimer's |
| `1004` | Mark Descarte | son and caregiver |
| `1005` | Bruce Jameson | in a meeting |
| `1006` | John Michaels | employee |
| `1007` | Stranger | unknown |
| `1008` | Gate AI Agent | reserved |

Special routes:

- `9001`: route to the local Gemini AudioSocket bridge (`Gate AI Agent`)
- `1001`: Emma scenario; Sarah connects directly after a short Gate prompt, unknown callers are rerouted to Sarah.
- `1003`: Olivia scenario; unknown callers are routed through Gate before caregiver handoff.
- `1005`: Bruce scenario; John is screened by Gate while Bruce is in a meeting, and only urgent calls are transferred.

## Notes

This MVP intentionally exposes SIP and RTP to the public internet. Treat the VM as disposable and keep extension passwords strong.
