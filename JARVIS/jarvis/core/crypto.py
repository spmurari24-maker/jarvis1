from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a passphrase and an independently stored salt."""
    if len(salt) < 16:
        raise ValueError("salt must contain at least 16 bytes")
    raw = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 600_000, dklen=32)
    return base64.urlsafe_b64encode(raw)


class EncryptedJsonStore:
    """Small encrypted-at-rest JSON store. Never writes plaintext to disk."""

    def __init__(self, path: str | Path, key: bytes | str):
        self.path = Path(path)
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def save(self, value: Any) -> None:
        token = self._fernet.encrypt(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_bytes(token)
        os.replace(temp_path, self.path)

    def load(self) -> Any:
        if not self.path.exists():
            return None
        try:
            plaintext = self._fernet.decrypt(self.path.read_bytes())
        except InvalidToken as exc:
            raise ValueError("Encrypted store key is invalid or the file was modified") from exc
        return json.loads(plaintext.decode("utf-8"))
