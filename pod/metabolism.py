"""The metabolism — the organs that earn what the pod owes.

skulth#4 frozen slice: ONE venue (plus the honestly-labeled MockVault),
a file-backed treasury, cognition priced in micro-USDC, and the deposit
gate seam — the Confirm engine wires in here later; until then anything
honoring the protocol. The death daemon judges at epoch close; this
module makes sure there is something to judge.

Stdlib only. Integer micro-USDC. Deterministic by construction — the mock
vault's yield is a schedule, never a die-roll: the demo must replay.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

from pod.death import ACTIVITY_NAME, DeathDaemon


class GateBlocked(RuntimeError):
    """The Confirm verdict was not 'cleared' — capital does not move."""


class InsufficientTreasury(RuntimeError):
    """Deposits spend real balance; debt is for judgments, not transfers."""


class DepositGate(Protocol):
    def verdict(self, venue_id: str) -> str: ...


class StaticGate:
    """Test/dev stand-in for the Confirm engine: a fixed verdict per venue."""

    def __init__(self, verdicts: dict[str, str]) -> None:
        self._verdicts = verdicts

    def verdict(self, venue_id: str) -> str:
        return self._verdicts.get(venue_id, "blocked")


class LedgerTreasury:
    """File-backed treasury. Balance may go negative — skuld means debt,
    and a pod in debt meets the daemon at epoch close. Transfers out
    (deposits) are refused beyond balance: you cannot send what you do
    not hold on-chain.
    """

    def __init__(self, state_dir: Path, opening_micro: int = 0) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.state_dir / "treasury.json"
        if self._file.exists():
            self._balance = json.loads(self._file.read_text())["balance_micro"]
        else:
            self._balance = opening_micro
            self._persist()

    def balance_micro(self) -> int:
        return self._balance

    def credit_micro(self, amount: int) -> None:
        self._balance += amount
        self._persist()

    def debit_micro(self, amount: int) -> None:
        self._balance -= amount
        self._persist()

    def _persist(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"balance_micro": self._balance}))
        tmp.replace(self._file)


class MockVault:
    """Deterministic yield venue — a simulation that preserves rent
    pressure, not a fake APY (benchmark 032 grab, Qwen's gift). The
    schedule is basis points per epoch; past its end, the last rate
    holds. Principal stays until the demo needs withdrawal (out of
    the frozen slice for now).
    """

    venue_id = "mock-vault"

    def __init__(self, rate_bps_schedule: list[int]) -> None:
        if not rate_bps_schedule:
            raise ValueError("schedule must not be empty")
        self._schedule = list(rate_bps_schedule)
        self.principal_micro = 0

    def deposit_micro(self, amount: int) -> None:
        self.principal_micro += amount

    def accrue_micro(self, epoch: int) -> int:
        rate = self._schedule[min(epoch, len(self._schedule) - 1)]
        return self.principal_micro * rate // 10_000


class CognitionMeter:
    """Thought has a price (skulth#4: the treasury-held choice-node).
    Local inference is free at the margin; frontier calls accumulate
    here and burn at epoch close.
    """

    def __init__(self) -> None:
        self.pending_micro = 0

    def record_frontier_call(self, cost_micro: int) -> None:
        self.pending_micro += cost_micro

    def consume(self) -> int:
        burned, self.pending_micro = self.pending_micro, 0
        return burned


@dataclass(frozen=True)
class EpochReport:
    epoch: int
    earned_micro: int
    burned_micro: int
    survived: bool
    balance_after_micro: int
    runway_epochs: Optional[int]  # None when next rent is zero


class Metabolism:
    """Per-epoch loop: harvest yield → burn cognition → face the daemon."""

    def __init__(
        self,
        treasury: LedgerTreasury,
        daemon: DeathDaemon,
        gate: DepositGate,
        cognition: CognitionMeter,
    ) -> None:
        self.treasury = treasury
        self.daemon = daemon
        self.gate = gate
        self.cognition = cognition
        self.venue = None

    def deposit(self, venue, amount_micro: int) -> None:
        verdict = self.gate.verdict(venue.venue_id)
        if verdict != "cleared":
            raise GateBlocked(f"{venue.venue_id}: verdict '{verdict}' — deposit blocked")
        if amount_micro > self.treasury.balance_micro():
            raise InsufficientTreasury(
                f"deposit {amount_micro} exceeds balance {self.treasury.balance_micro()}"
            )
        self.treasury.debit_micro(amount_micro)
        venue.deposit_micro(amount_micro)
        self.venue = venue

    def run_epoch(self, epoch: int) -> EpochReport:
        earned = self.venue.accrue_micro(epoch) if self.venue else 0
        if earned:
            self.treasury.credit_micro(earned)
        burned = self.cognition.consume()
        if burned:
            self.treasury.debit_micro(burned)
        survived = self.daemon.settle(epoch)
        balance = self.treasury.balance_micro()
        next_rent = self.daemon.rent.rent_due_micro(epoch + 1)
        runway = (balance // next_rent) if next_rent > 0 else None
        report = EpochReport(epoch, earned, burned, survived, balance, runway)
        self._log(report)
        return report

    def _log(self, report: EpochReport) -> None:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "epoch-report",
            **report.__dict__,
        }
        with (self.daemon.state_dir / ACTIVITY_NAME).open("a") as f:
            f.write(json.dumps(event) + "\n")
