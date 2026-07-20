"""Death-daemon harness — skulth#4 P6 discipline: the death path gets more
coverage than the life path, and the demo's kill switch is a test first.
"""

import json

import pytest

from pod.death import ACTIVITY_NAME, DeathDaemon, PodIsDead
from pod.epoch import EpochClock


class FakeTreasury:
    def __init__(self, micro: int) -> None:
        self._balance = micro

    def balance_micro(self) -> int:
        return self._balance

    def debit_micro(self, amount: int) -> None:
        self._balance -= amount


class StaticRent:
    def __init__(self, micro: int) -> None:
        self._micro = micro

    def rent_due_micro(self, epoch: int) -> int:
        return self._micro


RENT = 2_400_000  # 2.40 USDC per epoch — the twins' demo figure


def daemon(tmp_path, balance_micro, rent_micro=RENT, **kw):
    return DeathDaemon(tmp_path, FakeTreasury(balance_micro), StaticRent(rent_micro), **kw)


def activity(tmp_path):
    lines = (tmp_path / ACTIVITY_NAME).read_text().splitlines()
    return [json.loads(l) for l in lines]


# --- life path -------------------------------------------------------------


def test_survives_and_debits_rent(tmp_path):
    d = daemon(tmp_path, balance_micro=10_000_000)
    assert d.settle(epoch=1) is True
    assert d.treasury.balance_micro() == 10_000_000 - RENT
    assert not d.is_dead()
    assert activity(tmp_path)[-1]["action"] == "rent-settled"


def test_exact_balance_survives_to_zero(tmp_path):
    # Dummiþ dust edge: treasury lands EXACTLY on the rent — pays, lives, broke.
    d = daemon(tmp_path, balance_micro=RENT)
    assert d.settle(epoch=1) is True
    assert d.treasury.balance_micro() == 0


# --- death path ------------------------------------------------------------


def test_one_micro_short_dies(tmp_path):
    d = daemon(tmp_path, balance_micro=RENT - 1)
    assert d.settle(epoch=9) is False
    assert d.is_dead()


def test_death_record_is_verifiable(tmp_path):
    d = daemon(
        tmp_path,
        balance_micro=1_120_000,
        last_decision=lambda: "abstained (no consistent bundle)",
    )
    d.settle(epoch=9)
    record = json.loads(d.tombstone.read_text())
    assert record["schema"] == 1
    assert record["epoch"] == 9
    assert record["cause"] == "rent unpaid"
    assert record["final_balance_micro"] == 1_120_000
    assert record["rent_due_micro"] == RENT
    assert record["last_decision"] == "abstained (no consistent bundle)"
    assert "1.120000 USDC" in record["epitaph"]
    assert "2.400000 USDC" in record["epitaph"]
    assert record["died_at"]  # timestamped, ISO-8601


def test_insolvent_treasury_is_not_debited(tmp_path):
    # Death takes the record, never the remaining dust.
    d = daemon(tmp_path, balance_micro=1_000)
    d.settle(epoch=0)
    assert d.treasury.balance_micro() == 1_000


def test_death_logged_once_in_activity(tmp_path):
    d = daemon(tmp_path, balance_micro=0)
    d.settle(epoch=3)
    with pytest.raises(PodIsDead):
        d.settle(epoch=4)
    deaths = [e for e in activity(tmp_path) if e["action"] == "death"]
    assert len(deaths) == 1


# --- the zombie check ------------------------------------------------------


def test_dead_pod_refuses_restart(tmp_path):
    daemon(tmp_path, balance_micro=0).settle(epoch=1)
    with pytest.raises(PodIsDead, match="refusing restart"):
        daemon(tmp_path, balance_micro=999_000_000)  # riches cannot resurrect


def test_settle_after_death_raises(tmp_path):
    d = daemon(tmp_path, balance_micro=0)
    d.settle(epoch=1)
    with pytest.raises(PodIsDead):
        d.settle(epoch=2)


# --- the one clock ---------------------------------------------------------


def test_epoch_clock_is_deterministic():
    t = {"now": 1_000.0}
    clock = EpochClock(genesis=1_000.0, seconds_per_epoch=100.0, now=lambda: t["now"])
    assert clock.current() == 0
    t["now"] = 1_099.9
    assert clock.current() == 0
    t["now"] = 1_100.0
    assert clock.current() == 1
    assert clock.close_time(0) == 1_100.0
    assert clock.close_time(4) == 1_500.0


def test_epoch_clock_rejects_nonpositive_epoch_length():
    with pytest.raises(ValueError):
        EpochClock(genesis=0.0, seconds_per_epoch=0.0)


def test_epoch_clock_rejects_pre_genesis_reads():
    clock = EpochClock(genesis=1_000.0, seconds_per_epoch=100.0, now=lambda: 999.0)
    with pytest.raises(ValueError):
        clock.current()
