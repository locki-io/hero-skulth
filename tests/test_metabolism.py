"""Metabolism harness — the twins exist here as tests before they exist
as containers. Twin A earns and survives; twin B starves on schedule;
one expensive thought can kill.
"""

import pytest

from pod.death import DeathDaemon, PodIsDead
from pod.metabolism import (
    CognitionMeter,
    GateBlocked,
    InsufficientTreasury,
    LedgerTreasury,
    Metabolism,
    MockVault,
    StaticGate,
)

RENT = 2_400_000  # 2.40 USDC per epoch


class StaticRent:
    def rent_due_micro(self, epoch: int) -> int:
        return RENT


def pod(tmp_path, opening_micro, verdicts=None):
    treasury = LedgerTreasury(tmp_path, opening_micro)
    daemon = DeathDaemon(tmp_path, treasury, StaticRent())
    if verdicts is None:  # explicit: {} means "no venue cleared", not "default"
        verdicts = {"mock-vault": "cleared"}
    return Metabolism(treasury, daemon, gate=StaticGate(verdicts), cognition=CognitionMeter())


# --- treasury --------------------------------------------------------------


def test_ledger_persists_across_reload(tmp_path):
    t = LedgerTreasury(tmp_path, 5_000_000)
    t.credit_micro(1_000_000)
    t.debit_micro(300_000)
    assert LedgerTreasury(tmp_path).balance_micro() == 5_700_000


# --- the gate seam (LANDED criterion 4) ------------------------------------


def test_blocked_verdict_stops_capital(tmp_path):
    m = pod(tmp_path, 10_000_000, verdicts={"mock-vault": "blocked"})
    vault = MockVault([300])
    with pytest.raises(GateBlocked):
        m.deposit(vault, 5_000_000)
    assert m.treasury.balance_micro() == 10_000_000
    assert vault.principal_micro == 0


def test_unknown_venue_defaults_to_blocked(tmp_path):
    m = pod(tmp_path, 10_000_000, verdicts={})
    with pytest.raises(GateBlocked):
        m.deposit(MockVault([300]), 5_000_000)


def test_cleared_verdict_moves_capital(tmp_path):
    m = pod(tmp_path, 10_000_000)
    vault = MockVault([300])
    m.deposit(vault, 6_000_000)
    assert m.treasury.balance_micro() == 4_000_000
    assert vault.principal_micro == 6_000_000


def test_deposit_beyond_balance_refused(tmp_path):
    m = pod(tmp_path, 1_000_000)
    with pytest.raises(InsufficientTreasury):
        m.deposit(MockVault([300]), 5_000_000)


# --- deterministic yield ---------------------------------------------------


def test_mock_vault_replays_identically(tmp_path):
    def run(subdir):
        m = pod(tmp_path / subdir, 100_000_000)
        m.deposit(MockVault([180, 140, 90]), 90_000_000)
        return [m.run_epoch(e).earned_micro for e in range(5)]

    assert run("a") == run("b")
    # schedule exhausts → last rate holds
    assert run("c")[2:] == [810_000, 810_000, 810_000]


# --- the twins, in miniature -----------------------------------------------


def test_twin_a_earns_and_survives(tmp_path):
    m = pod(tmp_path, 100_000_000)
    m.deposit(MockVault([300]), 90_000_000)  # 2.70/epoch yield vs 2.40 rent
    reports = [m.run_epoch(e) for e in range(6)]
    assert all(r.survived for r in reports)
    assert reports[-1].balance_after_micro > reports[0].balance_after_micro - RENT


def test_twin_b_starves_on_schedule(tmp_path):
    m = pod(tmp_path, 7_200_000)  # exactly three rents, no yield: abstained
    assert m.run_epoch(0).survived
    assert m.run_epoch(1).survived
    r2 = m.run_epoch(2)
    assert r2.survived and r2.balance_after_micro == 0
    r3 = m.run_epoch(3)
    assert not r3.survived
    assert m.daemon.is_dead()


def test_runway_counts_down(tmp_path):
    m = pod(tmp_path, 7_200_000)
    assert m.run_epoch(0).runway_epochs == 2
    assert m.run_epoch(1).runway_epochs == 1
    assert m.run_epoch(2).runway_epochs == 0


def test_expensive_thought_hastens_death(tmp_path):
    # Same treasury as twin B, plus ONE frontier call worth an epoch of rent:
    # the pod dies one epoch earlier. The thought that killed the pod.
    m = pod(tmp_path, 7_200_000)
    m.cognition.record_frontier_call(RENT)
    assert m.run_epoch(0).survived
    assert m.run_epoch(1).survived
    assert not m.run_epoch(2).survived  # twin B survived this one


def test_dead_pod_cannot_metabolize(tmp_path):
    m = pod(tmp_path, 0)
    m.run_epoch(0)
    with pytest.raises(PodIsDead):
        m.run_epoch(1)
