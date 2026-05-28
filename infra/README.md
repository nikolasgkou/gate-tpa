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
| `1008` | Gate AI Agent | AI screener |

Special routes:

- `9001`: route to Azure OpenAI Realtime SIP (`Gate AI Agent`)

## Notes

This MVP intentionally exposes SIP and RTP to the public internet. Treat the VM as disposable and keep extension passwords strong.
