# Apple App Store Server API key — production install

Used for **outbound** App Store Server API calls (Sandbox Request / Get Test Notification).
Inbound ASN V2 verification uses public Apple root CAs only and does **not** need this key.

## Environment variables

| Variable | Purpose |
|---|---|
| `IAP_APPLE_ASC_ISSUER_ID` | App Store Connect → Users and Access → Integrations → In-App Purchase → **Issuer ID** (UUID) |
| `IAP_APPLE_ASC_KEY_ID` | Key ID of the In-App Purchase API key (e.g. `4N9N354RG3`) |
| `IAP_APPLE_ASC_PRIVATE_KEY_PATH` | Absolute path to the downloaded `.p8` on the VPS |

Keep `IAP_APPLE_PURCHASING_ENABLED=false` and `IAP_APPLE_CREDIT_ENABLED=false` during C1.

## Secure filesystem location (production)

```text
/var/lib/fashionrise/secrets/apple-iap/
  AuthKey_<KEYID>.p8     # mode 600, owner fashionriseapp:fashionriseapp
  INSTALL.owner.txt      # these instructions
```

Directory mode **750**, owner **fashionriseapp:fashionriseapp**. Outside the git checkout.

## Owner: transfer the `.p8` (do not paste into chat)

On the machine that holds the downloaded key (typical name `SubscriptionKey_4N9N354RG3.p8` or `AuthKey_4N9N354RG3.p8`):

```bash
# Replace LOCAL_P8 with the real download path. Do not commit or chat the file contents.
scp "$HOME/Downloads/SubscriptionKey_4N9N354RG3.p8" \
  root@YOUR_VPS_HOST:/var/lib/fashionrise/secrets/apple-iap/AuthKey_4N9N354RG3.p8
```

Then on the VPS as root:

```bash
chown fashionriseapp:fashionriseapp \
  /var/lib/fashionrise/secrets/apple-iap/AuthKey_4N9N354RG3.p8
chmod 600 /var/lib/fashionrise/secrets/apple-iap/AuthKey_4N9N354RG3.p8
# Confirm presence without dumping the key:
sudo -u fashionriseapp head -1 /var/lib/fashionrise/secrets/apple-iap/AuthKey_4N9N354RG3.p8
# Expect: -----BEGIN PRIVATE KEY-----
```

Set Issuer ID in `/opt/fashionrise/src/backend/.env` (edit on server only):

```env
IAP_APPLE_ASC_ISSUER_ID=<paste-issuer-uuid-from-ASC>
IAP_APPLE_ASC_KEY_ID=4N9N354RG3
IAP_APPLE_ASC_PRIVATE_KEY_PATH=/var/lib/fashionrise/secrets/apple-iap/AuthKey_4N9N354RG3.p8
IAP_APPLE_PURCHASING_ENABLED=false
IAP_APPLE_CREDIT_ENABLED=false
```

Optional one-line drop file (agent can read without opening chat):

```bash
# exact one-line UUID, mode 600
printf '%s\n' '<issuer-uuid>' > /var/lib/fashionrise/secrets/apple-iap/ISSUER_ID
chown fashionriseapp:fashionriseapp /var/lib/fashionrise/secrets/apple-iap/ISSUER_ID
chmod 600 /var/lib/fashionrise/secrets/apple-iap/ISSUER_ID
```

Signal ready:

```bash
touch /var/lib/fashionrise/secrets/apple-iap/READY
chown fashionriseapp:fashionriseapp /var/lib/fashionrise/secrets/apple-iap/READY
```

## Ops check (after install)

```bash
cd /opt/fashionrise/src/backend
sudo -u fashionriseapp /opt/fashionrise/.venv/bin/python \
  scripts/request_apple_asn_test.py check-config
```

Then (authorized once):

```bash
sudo -u fashionriseapp /opt/fashionrise/.venv/bin/python \
  scripts/request_apple_asn_test.py request-once
sudo -u fashionriseapp /opt/fashionrise/.venv/bin/python \
  scripts/request_apple_asn_test.py status \
  --token-file /var/lib/fashionrise/secrets/apple-iap/last-test-notification.token
```
