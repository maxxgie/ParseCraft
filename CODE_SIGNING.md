# Code Signing

## Environment variables

- SIGNING_ENABLED=true|false
- PFX_CERTIFICATE_PATH=path to .pfx
- PFX_CERTIFICATE_PASSWORD=password
- TIMESTAMP_SERVER=http://timestamp.digicert.com

## Local signed build

```powershell
$env:SIGNING_ENABLED="true"
$env:PFX_CERTIFICATE_PATH="C:\certificates\ParseCraftCert.pfx"
$env:PFX_CERTIFICATE_PASSWORD="password"
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

## GitHub Actions

Set secrets SIGNING_CERTIFICATE (base64 .pfx) and SIGNING_PASSWORD. The workflow decodes and signs automatically.

## Security

Never commit .pfx or passwords. They are gitignored.