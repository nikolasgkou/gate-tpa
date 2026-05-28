# Gate TPA PBX Infrastructure

This deploys the MVP SIP target: an Azure-hosted Asterisk PBX for Linphone clients.

## Resources

- Ubuntu VM running Asterisk.
- Static public IP with DNS label.
- Network security group allowing:
  - `22/TCP` for SSH.
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

Use these Linphone fields:

- Username: `1001`, `1002`, or `1003`
- Auth username: same as username
- Password: same as username
- Domain/SIP server: deployment output `publicIpAddress` or `fqdn`
- Transport: `UDP`
- Port: `5060`
- Test call: dial `600` for echo test

## Notes

This MVP intentionally exposes SIP and RTP to the public internet. Treat the VM as disposable and keep extension passwords strong.
