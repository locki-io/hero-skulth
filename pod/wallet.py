"""The pod's hand — programmatic wallet birth (Arc is EVM; an address is math).

Two custody designs, both served, operator chooses (skulth#4 N1):

(a) OPERATOR-MINTED — `python -m pod.wallet` prints a fresh keypair ONCE
    to the terminal that ran it. Run it in YOUR terminal, never through an
    agent shell: transcripts remember. Paste the key into `.env.apps` as
    `SKULTH_POD_WALLET_KEY` per the template.

(b) POD-BORN — `ensure_wallet(state_dir)` mints at first breath; the key
    lives ONLY in the sealed state dir (0600, gitignored, volume-bound)
    and this module never returns it — callers get the ADDRESS. No human
    ever holds the private key; rotation = a new life; the operator's
    kill switch (volume destruction) is also key destruction.

Uses eth-account (MIT, Ethereum Foundation) — the minimal subset of the
ONE dependency P2 admitted (web3/Arc SDK scope; gauntlet passed
2026-07-20: MIT license, canonical maintainer, venv-pinned 0.13.7).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from eth_account import Account

WALLET_NAME = "wallet.json"


def ensure_wallet(state_dir: Path) -> str:
    """Pod-born custody: create on first call, return the ADDRESS (only).
    Idempotent — a life keeps its hand; only a new life gets a new one."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    wallet_file = state_dir / WALLET_NAME
    if wallet_file.exists():
        return json.loads(wallet_file.read_text())["address"]
    account = Account.create()  # entropy from os.urandom
    payload = json.dumps({"address": account.address, "private_key": account.key.hex()})
    tmp = wallet_file.with_suffix(".tmp")
    tmp.touch(mode=0o600)
    tmp.write_text(payload)
    tmp.replace(wallet_file)
    os.chmod(wallet_file, 0o600)
    return account.address


def address(state_dir: Path) -> str | None:
    """The public face of the hand, or None if no wallet was born yet."""
    wallet_file = Path(state_dir) / WALLET_NAME
    if not wallet_file.exists():
        return None
    return json.loads(wallet_file.read_text())["address"]


def _signing_key(state_dir: Path) -> str:
    """Internal: the chain organ (payRent, Teller) loads it here — the key
    never crosses a module boundary as a return value elsewhere."""
    return json.loads((Path(state_dir) / WALLET_NAME).read_text())["private_key"]


def main() -> int:
    """Design (a): print a fresh keypair ONCE, for the operator's eyes."""
    account = Account.create()
    print("# hero-skulth wallet — printed ONCE, never logged. Operator custody.")
    print(f"# address (public — for faucet + allowlist ticket): {account.address}")
    print(f"SKULTH_POD_WALLET_KEY={account.key.hex()}")
    print("# paste the line above into pod/.env.apps — then clear this terminal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
