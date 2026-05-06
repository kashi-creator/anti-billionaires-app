#!/usr/bin/env python3
"""Generate a VAPID keypair for Web Push.

Run once per deployment environment. Save the printed values into Railway
(or your local .env) as:

    VAPID_PUBLIC_KEY   — base64url, sent to browsers
    VAPID_PRIVATE_KEY  — base64url, kept on the server
    VAPID_CLAIM_EMAIL  — mailto: or https:// you control (push services log it)

Usage:
    python scripts/generate_vapid_keys.py
"""
import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # Private: raw 32-byte scalar
    private_numbers = private_key.private_numbers()
    private_bytes = private_numbers.private_value.to_bytes(32, "big")

    # Public: uncompressed 65-byte point (0x04 || X || Y)
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    print("# --- Sovereign Society — VAPID keypair ---")
    print("# Paste each line into Railway → Variables. Save in 1Password too.")
    print("#")
    print("# !! DO NOT paste the PRIVATE key back into chat, Slack, email, or")
    print("#    any AI assistant. It controls every push notification this app")
    print("#    can ever send. If exposed, re-run this script (rotates keys)")
    print("#    and update Railway — every existing subscription will break.")
    print()
    print(f"VAPID_PUBLIC_KEY={b64url(public_bytes)}")
    print(f"VAPID_PRIVATE_KEY={b64url(private_bytes)}    # SECRET — DO NOT SHARE")
    print("VAPID_CLAIM_EMAIL=mailto:kashi@thebreathcoachschool.com")


if __name__ == "__main__":
    main()
