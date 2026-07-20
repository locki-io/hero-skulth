"""Valþyria harness — the decision seat under every kind of doubt.
Abstention paths outnumber deposit paths, as they should.
"""

from pod.regime import resolve_regime
from pod.valthyria import VenueProfile, decide

RENT = 2_400_000


def healthy(**over):
    base = dict(
        venue_id="mock-vault",
        yield_bps=300,
        audit_count=3,
        exploit_count=0,
        withdrawal_latency_epochs=0,
    )
    base.update(over)
    return VenueProfile(**base)


def run(profile, *, verdict="cleared", regime="neutral", balance=100_000_000,
        proposed=90_000_000, reserve=3):
    return decide(
        profile,
        gate_verdict=verdict,
        regime=regime,
        balance_micro=balance,
        rent_micro=RENT,
        proposed_micro=proposed,
        reserve_epochs=reserve,
    )


# --- Eliminate ---------------------------------------------------------------


def test_gate_verdict_eliminates_first():
    d = run(healthy(), verdict="blocked")
    assert d.action == "abstain" and "capital does not move" in d.reasons[0]


def test_exploit_history_is_weight_zero():
    d = run(healthy(exploit_count=1))
    assert d.action == "abstain" and "exploit history" in d.reasons[0]


def test_withdrawal_latency_beyond_runway_abstains():
    # runway = 100/2.4 = 41 epochs; latency 50 means no exit before rent day
    d = run(healthy(withdrawal_latency_epochs=50))
    assert d.action == "abstain" and "withdrawal latency" in d.reasons[0]


# --- Weigh × Probabilize -----------------------------------------------------


def test_healthy_venue_neutral_regime_deposits():
    d = run(healthy())
    assert d.action == "deposit"
    assert d.amount_micro == 90_000_000
    assert d.weight >= 0.5


def test_crisis_regime_flips_same_venue_to_abstain():
    # Twin B's fate as a test: identical venue, regime crisis → doubt wins.
    d = run(healthy(), regime="crisis")
    assert d.action == "abstain"
    assert any("doubt is an asset" in r for r in d.reasons)


def test_thin_audits_cannot_carry_a_defensive_regime():
    d = run(healthy(audit_count=1), regime="defensive")
    assert d.action == "abstain"


def test_deep_audits_survive_a_defensive_regime():
    d = run(healthy(audit_count=3), regime="defensive")
    assert d.action == "deposit"


# --- Reserve floor -----------------------------------------------------------


def test_reserve_floor_blocks_a_broke_pod():
    # 7.2 balance − 3×2.4 reserve = 0 available: correct abstention, twin B's bind
    d = run(healthy(), balance=7_200_000, proposed=90_000_000)
    assert d.action == "abstain"
    assert any("reserve floor" in r for r in d.reasons)


def test_deposit_is_capped_by_reserve():
    # 10 USDC balance, reserve 7.2 → only 2.8 may move, whatever was proposed
    d = run(healthy(), balance=10_000_000, proposed=90_000_000)
    assert d.action == "deposit" and d.amount_micro == 2_800_000


def test_decisions_are_deterministic_and_reasoned():
    a, b = run(healthy()), run(healthy())
    assert a == b
    assert len(a.reasons) >= 2


# --- The regime seam ---------------------------------------------------------


def test_env_override_wins():
    regime, provenance = resolve_regime({"SKULTH_POD_REGIME": "crisis"})
    assert regime == "crisis" and "override" in provenance


def test_unknown_override_degrades_to_neutral():
    regime, _ = resolve_regime({"SKULTH_POD_REGIME": "moonshot"})
    assert regime == "neutral"


def test_unreachable_api_degrades_never_raises():
    regime, provenance = resolve_regime(
        {
            "SKULTH_API_URL": "http://127.0.0.1:1",  # nothing listens on port 1
            "SKULTH_API_KEY_POD": "k",
            "SKULTH_API_SECRET_POD": "s",
        }
    )
    assert regime == "neutral" and "degraded" in provenance


def test_no_source_is_honest_neutral():
    regime, provenance = resolve_regime({})
    assert regime == "neutral" and "no source" in provenance
