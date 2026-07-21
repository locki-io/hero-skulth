"""The death daemon — the organ that makes the autonomy honest.

skulth#4 LANDED criterion 3: when the treasury cannot pay at epoch close,
the pod writes a verifiable death record, stops, and STAYS dead. The
tombstone IS the record; resurrection means an operator deletes it — the
pod cannot reach its own kill infrastructure from inside its process.

Stdlib only: survival machinery carries no dependency risk.
Money is integer micro-USDC (6 decimals); floats never touch the ledger.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

TOMBSTONE_NAME = "TOMBSTONE.json"
ACTIVITY_NAME = "pod-activity.jsonl"


class Treasury(Protocol):
    def balance_micro(self) -> int: ...

    def debit_micro(self, amount: int) -> None: ...


class RentSchedule(Protocol):
    def rent_due_micro(self, epoch: int) -> int: ...


class PodIsDead(RuntimeError):
    """Raised on any attempt to run a pod whose tombstone exists."""


def _usdc(micro: int) -> str:
    return f"{micro / 1_000_000:.6f} USDC"


class DeathDaemon:
    """Judges solvency at epoch close; executes death; enforces the zombie check.

    Scheduling belongs to the ticker, payment rails to the metabolism —
    this organ only judges and, when judgment falls, writes the record.
    """

    def __init__(
        self,
        state_dir: Path,
        treasury: Treasury,
        rent: RentSchedule,
        last_decision: Callable[[], str] = lambda: "none recorded",
    ) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.treasury = treasury
        self.rent = rent
        self.last_decision = last_decision
        self.assert_alive()

    @property
    def tombstone(self) -> Path:
        return self.state_dir / TOMBSTONE_NAME

    def is_dead(self) -> bool:
        return self.tombstone.exists()

    def assert_alive(self) -> None:
        if self.is_dead():
            epitaph = json.loads(self.tombstone.read_text())["epitaph"]
            raise PodIsDead(f"dead — refusing restart: {epitaph}")

    def settle(self, epoch: int) -> bool:
        """Epoch-close judgment: pay the rent or die. Returns True iff survived."""
        self.assert_alive()
        due = self.rent.rent_due_micro(epoch)
        balance = self.treasury.balance_micro()
        if balance < due:
            self._die(
                epoch=epoch,
                cause="rent unpaid",
                final_balance_micro=balance,
                rent_due_micro=due,
            )
            return False
        self.treasury.debit_micro(due)
        self._log(
            {
                "action": "rent-settled",
                "epoch": epoch,
                "rent_micro": due,
                "balance_after_micro": self.treasury.balance_micro(),
            }
        )
        return True

    def _die(
        self, *, epoch: int, cause: str, final_balance_micro: int, rent_due_micro: int
    ) -> None:
        if self.is_dead():  # idempotent: one tombstone, ever
            return
        record = {
            "schema": 1,
            "died_at": datetime.now(timezone.utc).isoformat(),
            "epoch": epoch,
            "cause": cause,
            "final_balance_micro": final_balance_micro,
            "rent_due_micro": rent_due_micro,
            "last_decision": self.last_decision(),
            "epitaph": (
                f"epoch {epoch}: {cause} — treasury {_usdc(final_balance_micro)}"
                f" < rent {_usdc(rent_due_micro)}"
            ),
        }
        tmp = self.tombstone.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2))
        tmp.replace(self.tombstone)  # atomic: no half-written tombstones
        self._log({"action": "death", **record})

    def _log(self, event: dict) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        with (self.state_dir / ACTIVITY_NAME).open("a") as f:
            f.write(json.dumps(event) + "\n")
            f.flush()
            os.fsync(f.fileno())  # a hard host stop must not tear the life ledger
