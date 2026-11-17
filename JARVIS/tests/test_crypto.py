import pytest
from cryptography.fernet import Fernet

from jarvis.core.crypto import EncryptedJsonStore


def test_encrypted_store_round_trips_without_plaintext(tmp_path):
    path = tmp_path / "private.json.enc"
    store = EncryptedJsonStore(path, Fernet.generate_key())
    store.save({"note": "private value"})
    assert store.load() == {"note": "private value"}
    assert b"private value" not in path.read_bytes()


def test_wrong_key_does_not_return_data(tmp_path):
    path = tmp_path / "private.enc"
    EncryptedJsonStore(path, Fernet.generate_key()).save({"private": True})
    with pytest.raises(ValueError):
        EncryptedJsonStore(path, Fernet.generate_key()).load()
