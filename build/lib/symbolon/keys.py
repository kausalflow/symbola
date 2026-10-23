"""Runner signing keys (Ed25519) and DSSE envelopes.

Attestations are in-toto statements wrapped in a DSSE envelope. The
signature covers the DSSE pre-authentication encoding (PAE) of the payload,
as the DSSE spec requires: https://github.com/secure-systems-lab/dsse
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

DEFAULT_KEY = Path(os.environ.get("SYMBOLON_HOME", Path.home() / ".config" / "symbolon")) / "runner.key"
PAYLOAD_TYPE = "application/vnd.in-toto+json"


def generate(path: Path = DEFAULT_KEY) -> Path:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    public_path(path).write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return path


def public_path(key_path: Path) -> Path:
    return Path(key_path).with_suffix(".pub")


def load_private(path: Path = DEFAULT_KEY) -> Ed25519PrivateKey:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no runner key at {path}; run `symbolon keygen` first")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 key")
    return key


def load_public(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(f"{path} is not an Ed25519 public key")
    return key


def raw_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def keyid(key: Ed25519PublicKey) -> str:
    return "ed25519:" + hashlib.sha256(raw_public(key)).hexdigest()


def public_from_b64(value: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(value))


def pae(payload_type: str, payload: bytes) -> bytes:
    t = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(payload), payload)


def sign_envelope(payload: bytes, key: Ed25519PrivateKey) -> dict:
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [{
            "keyid": keyid(key.public_key()),
            "sig": base64.b64encode(key.sign(pae(PAYLOAD_TYPE, payload))).decode(),
        }],
    }


def verify_envelope(envelope: dict, key: Ed25519PublicKey) -> bytes:
    """Return the payload if one of the envelope's signatures is valid for `key`."""
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        raise ValueError(f"unexpected payloadType {envelope.get('payloadType')!r}")
    payload = base64.b64decode(envelope["payload"])
    wanted = keyid(key)
    for sig in envelope.get("signatures", []):
        if sig.get("keyid") != wanted:
            continue
        try:
            key.verify(base64.b64decode(sig["sig"]), pae(PAYLOAD_TYPE, payload))
        except InvalidSignature:
            raise ValueError("signature does not match the payload") from None
        return payload
    raise ValueError(f"no signature from {wanted}")
