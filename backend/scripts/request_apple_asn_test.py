"""Request exactly one Apple Sandbox ASN V2 TEST notification (ops only).

Requires production env (gates may stay OFF):

  IAP_APPLE_ASC_ISSUER_ID
  IAP_APPLE_ASC_KEY_ID
  IAP_APPLE_ASC_PRIVATE_KEY_PATH   # absolute path to .p8 outside the repo

Usage (from backend/, venv active):

  python scripts/request_apple_asn_test.py check-config
  python scripts/request_apple_asn_test.py request-once
  python scripts/request_apple_asn_test.py status --token-file /tmp/fr-asn-test.token

Never prints the full testNotificationToken, signedPayload, or private key.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services import apple_iap


def _redact_token(token: str) -> str:
    t = (token or "").strip()
    if len(t) <= 12:
        return "***"
    return f"{t[:6]}…{t[-4:]}(len={len(t)})"


def cmd_check_config(_: argparse.Namespace) -> int:
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()
    s = get_settings()
    path = (s.iap_apple_asc_private_key_path or "").strip()
    path_ok = bool(path) and Path(path).is_file()
    print(
        json.dumps(
            {
                "asc_api_configured": apple_iap.apple_asc_api_configured(),
                "inbound_verifier_configured": apple_iap.apple_iap_configured(),
                "bundle_id": s.iap_apple_bundle_id,
                "app_apple_id": s.iap_apple_app_apple_id,
                "key_id_set": bool((s.iap_apple_asc_key_id or "").strip()),
                "issuer_id_set": bool((s.iap_apple_asc_issuer_id or "").strip()),
                "private_key_path_set": bool(path),
                "private_key_file_present": path_ok,
                "purchasing_enabled": bool(s.iap_apple_purchasing_enabled),
                "credit_enabled": bool(s.iap_apple_credit_enabled),
                "unverified_sandbox": bool(s.iap_allow_unverified_sandbox),
            },
            indent=2,
        )
    )
    return 0 if apple_iap.apple_asc_api_configured() else 2


def cmd_request_once(args: argparse.Namespace) -> int:
    get_settings.cache_clear()
    if not apple_iap.apple_asc_api_configured():
        print("ERROR: ASC API not configured", file=sys.stderr)
        return 2
    s = get_settings()
    if s.iap_apple_purchasing_enabled or s.iap_apple_credit_enabled:
        print("ERROR: refusing to run while purchasing/credit gate is ON", file=sys.stderr)
        return 3

    token = apple_iap.request_sandbox_test_notification()
    out = Path(args.token_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(token + "\n")
    out.chmod(0o600)
    print(
        json.dumps(
            {
                "ok": True,
                "environment": "Sandbox",
                "test_notification_token_redacted": _redact_token(token),
                "token_file": str(out),
            },
            indent=2,
        )
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    get_settings.cache_clear()
    token = ""
    if args.token_file:
        token = Path(args.token_file).read_text().strip()
    elif args.token:
        token = args.token.strip()
    if not token:
        print("ERROR: provide --token-file or --token", file=sys.stderr)
        return 2

    last: dict | None = None
    for i in range(max(1, args.attempts)):
        last = apple_iap.get_sandbox_test_notification_status(token)
        print(
            json.dumps(
                {
                    "poll": i + 1,
                    "token_redacted": _redact_token(token),
                    **last,
                },
                indent=2,
            )
        )
        results = [a.get("result") for a in last.get("attempts") or []]
        if any(r == "SUCCESS" for r in results):
            return 0
        if last.get("attempt_count", 0) > 0 and i + 1 < args.attempts:
            time.sleep(args.sleep_seconds)
            continue
        if i + 1 < args.attempts:
            time.sleep(args.sleep_seconds)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check-config", help="Show ASC API configuration readiness")
    p_check.set_defaults(func=cmd_check_config)

    p_req = sub.add_parser("request-once", help="Request exactly one Sandbox TEST notification")
    p_req.add_argument(
        "--token-file",
        default="/var/lib/fashionrise/secrets/apple-iap/last-test-notification.token",
        help="0600 file to store the token (never printed in full)",
    )
    p_req.set_defaults(func=cmd_request_once)

    p_st = sub.add_parser("status", help="Poll Apple Get Test Notification Status")
    p_st.add_argument("--token-file", default="")
    p_st.add_argument("--token", default="")
    p_st.add_argument("--attempts", type=int, default=8)
    p_st.add_argument("--sleep-seconds", type=float, default=5.0)
    p_st.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
