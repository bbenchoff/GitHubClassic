#!/usr/bin/env python3
"""Regenerate synthetic vault fixtures (requires Python cryptography)."""
import argparse
import hashlib
from pathlib import Path
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]


def array(name, data):
    return "static const unsigned char " + name + "[]={" + ",".join(
        "0x%02x" % value for value in data) + "};\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    random = bytes(range(28))
    plain = b"legacy test authorization"
    rounds = 600000
    header = (b"GHVA0001" + struct.pack(">II", 1, rounds) + random
              + struct.pack(">I", len(plain)))
    key = hashlib.pbkdf2_hmac("sha256", b"weak", random[:16], rounds, 32)
    encoded = header + AESGCM(key).encrypt(random[16:], plain, header)
    text = ("/* Synthetic legacy envelope from Python hashlib and cryptography AESGCM. */\n"
            + array("legacy_vault", encoded) + array("legacy_key", key))
    target = ROOT / "tests/vault_vectors.h"
    if args.check:
        if target.read_text() != text:
            parser.error("vault fixture differs; regenerate and review")
        print("Vault fixture matches independent Python implementations")
    else:
        target.write_text(text, newline="\n")


if __name__ == "__main__":
    main()
