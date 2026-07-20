"""Valþyria — the decision seat: survival-first allocation.

Frame → Weigh → Probabilize → Eliminate, and abstention is ALWAYS in the
candidate set. The utility is P(rent paid at epoch N), never APY
(skulth#4 P2: ONE decision, done excellently). Every decision carries
its reasons — legibility is a survival trait too: the tombstone quotes
the last decision, and a judge may quote the tombstone.

Deterministic and stdlib-only, like every organ before it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Regime multipliers — the "follow economics to lower the risk" leg.
# Fed by skulþ's situation codes via pod/regime.py; unknown regimes
# read as neutral (degraded, never blind-bullish).
REGIME_FACTOR = {
    "expansion": 1.0,
    "neutral": 0.85,
    "defensive": 0.6,
    "crisis": 0.3,
}
DECISION_THRESHOLD = 0.5
AUDIT_SATURATION = 3  # audits beyond this add no weight — diminishing trust


@dataclass(frozen=True)
class VenueProfile:
    """The Frame: what is knowable about a venue before capital moves.
    Today these facts arrive from config (mock vault, honestly labeled);
    the Confirm engine's audit bundles replace them at the same seam.
    """

    venue_id: str
    yield_bps: int
    audit_count: int
    exploit_count: int
    withdrawal_latency_epochs: int


@dataclass(frozen=True)
class Decision:
    action: str  # "deposit" | "abstain"
    amount_micro: int
    weight: float
    regime: str
    reasons: tuple[str, ...]

    def summary(self) -> str:
        head = (
            f"deposited {self.amount_micro / 1_000_000:.2f} USDC"
            if self.action == "deposit"
            else "abstained"
        )
        return f"{head} [{self.regime}] — " + "; ".join(self.reasons)


def _abstain(regime: str, reasons: list[str]) -> Decision:
    return Decision("abstain", 0, 0.0, regime, tuple(reasons))


def decide(
    profile: VenueProfile,
    *,
    gate_verdict: str,
    regime: str,
    balance_micro: int,
    rent_micro: int,
    proposed_micro: int,
    reserve_epochs: int = 3,
) -> Decision:
    """The one decision: does this USDC enter contract X — or abstain?"""
    reasons: list[str] = []

    # --- Eliminate (hard exits; order = severity) ---
    if gate_verdict != "cleared":
        reasons.append(f"gate verdict '{gate_verdict}' — capital does not move")
        return _abstain(regime, reasons)
    if profile.exploit_count > 0:
        reasons.append(f"exploit history ({profile.exploit_count}) — weight zero")
        return _abstain(regime, reasons)
    runway_epochs = balance_micro // rent_micro if rent_micro else 0
    if profile.withdrawal_latency_epochs >= max(runway_epochs, 1):
        reasons.append(
            f"withdrawal latency {profile.withdrawal_latency_epochs}ep ≥ runway "
            f"{runway_epochs}ep — could not exit before rent day"
        )
        return _abstain(regime, reasons)

    # --- Weigh (ponderation: audit posture + rent coverage) ---
    audit_score = min(profile.audit_count, AUDIT_SATURATION) / AUDIT_SATURATION
    yield_per_epoch = proposed_micro * profile.yield_bps // 10_000
    coverage = min(yield_per_epoch / rent_micro, 1.0) if rent_micro else 0.0
    weight = round(0.5 * audit_score + 0.5 * coverage, 3)
    reasons.append(f"weight {weight} (audits {audit_score:.2f} · coverage {coverage:.2f})")

    # --- Probabilize (regime multiplier from skulþ's codes) ---
    factor = REGIME_FACTOR.get(regime, REGIME_FACTOR["neutral"])
    score = round(weight * factor, 3)
    reasons.append(f"× regime {regime} ({factor}) = {score}")
    if score < DECISION_THRESHOLD:
        reasons.append("below threshold — doubt is an asset; idle beats unvetted")
        return _abstain(regime, reasons)

    # --- Reserve floor (survival-first: N epochs stay liquid, always) ---
    available = balance_micro - reserve_epochs * rent_micro
    if available <= 0:
        reasons.append(f"reserve floor — keeping {reserve_epochs} epochs of rent liquid")
        return _abstain(regime, reasons)

    amount = min(proposed_micro, available)
    reasons.append(f"reserve holds {reserve_epochs} epochs; deploying {amount / 1_000_000:.2f}")
    return Decision("deposit", amount, score, regime, tuple(reasons))
