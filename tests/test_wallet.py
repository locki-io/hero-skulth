"""Wallet harness — the hand is born valid, keeps itself, and shows only
its public face.
"""

import json
import stat

from pod.wallet import WALLET_NAME, address, ensure_wallet


def test_wallet_is_born_valid(tmp_path):
    addr = ensure_wallet(tmp_path)
    assert addr.startswith("0x") and len(addr) == 42
    int(addr, 16)  # valid hex throughout


def test_a_life_keeps_its_hand(tmp_path):
    first = ensure_wallet(tmp_path)
    second = ensure_wallet(tmp_path)
    assert first == second  # idempotent — no silent key rotation mid-life


def test_two_lives_two_hands(tmp_path):
    a = ensure_wallet(tmp_path / "a")
    b = ensure_wallet(tmp_path / "b")
    assert a != b


def test_key_file_is_owner_only(tmp_path):
    ensure_wallet(tmp_path)
    mode = stat.S_IMODE((tmp_path / WALLET_NAME).stat().st_mode)
    assert mode == 0o600


def test_public_face_shows_no_key(tmp_path):
    ensure_wallet(tmp_path)
    assert address(tmp_path).startswith("0x")
    # the stored key exists but ensure_wallet/address never return it
    stored = json.loads((tmp_path / WALLET_NAME).read_text())
    assert "private_key" in stored
    assert address(tmp_path) == stored["address"]


def test_no_wallet_no_face(tmp_path):
    assert address(tmp_path) is None
