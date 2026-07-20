"""The twin runner — a pod's whole life as one process.

deploy/compose.yaml runs two of these: twin A earns and survives, twin B
abstains and starves. The organs are proven in the harness; this module
only wires them to the clock and keeps honest logs.

Death is exit code 3 — and a restarted corpse exits 3 again: the
tombstone refuses before any wiring happens. All state (treasury,
genesis, venue, decision, tombstone, activity) lives in one state dir,
so a container restart resumes a life but never restarts one.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from pod.death import DeathDaemon, PodIsDead
from pod.epoch import EpochClock
from pod.metabolism import CognitionMeter, LedgerTreasury, Metabolism, MockVault, StaticGate
from pod.regime import resolve_regime
from pod.valthyria import VenueProfile, decide

DEATH_EXIT = 3


@dataclass(frozen=True)
class TwinConfig:
    name: str
    opening_micro: int
    deposit_micro: int  # the PROPOSED allocation — Valþyria decides what actually moves
    vault_bps: list[int]
    vault_audits: int
    vault_exploits: int
    vault_latency_epochs: int
    rent_micro: int
    epoch_seconds: float
    reserve_epochs: int
    regime: str
    regime_provenance: str
    state_dir: Path

    @classmethod
    def from_env(cls, env: dict) -> "TwinConfig":
        regime, provenance = resolve_regime(env)
        return cls(
            name=env.get("SKULTH_POD_NAME", "twin"),
            opening_micro=int(env.get("SKULTH_POD_OPENING_MICRO", "0")),
            deposit_micro=int(env.get("SKULTH_POD_DEPOSIT_MICRO", "0")),
            vault_bps=[int(x) for x in env.get("SKULTH_POD_VAULT_BPS", "300").split(",")],
            vault_audits=int(env.get("SKULTH_POD_VAULT_AUDITS", "1")),
            vault_exploits=int(env.get("SKULTH_POD_VAULT_EXPLOITS", "0")),
            vault_latency_epochs=int(env.get("SKULTH_POD_VAULT_LATENCY_EPOCHS", "0")),
            rent_micro=int(env.get("SKULTH_POD_RENT_MICRO", "2400000")),
            epoch_seconds=float(env.get("SKULTH_POD_EPOCH_SECONDS", "3600")),
            reserve_epochs=int(env.get("SKULTH_POD_RESERVE_EPOCHS", "3")),
            regime=regime,
            regime_provenance=provenance,
            state_dir=Path(env.get("SKULTH_POD_STATE_DIR", "/state")),
        )


class ConfigRent:
    def __init__(self, micro: int) -> None:
        self._micro = micro

    def rent_due_micro(self, epoch: int) -> int:
        return self._micro


def _usdc(micro: int) -> str:
    return f"{micro / 1_000_000:.2f}"


def build_twin(cfg: TwinConfig) -> tuple[Metabolism, EpochClock]:
    """Wire a twin from persistent state. Raises PodIsDead on a tombstone —
    the corpse check runs before any money moves."""
    state = cfg.state_dir
    state.mkdir(parents=True, exist_ok=True)

    decision_file = state / "decision.txt"
    treasury = LedgerTreasury(state, cfg.opening_micro)
    daemon = DeathDaemon(
        state,
        treasury,
        ConfigRent(cfg.rent_micro),
        last_decision=lambda: decision_file.read_text().strip()
        if decision_file.exists()
        else "none recorded",
    )

    venue_file = state / "venue.json"
    principal = (
        json.loads(venue_file.read_text())["principal_micro"] if venue_file.exists() else 0
    )
    vault = MockVault(cfg.vault_bps, principal_micro=principal)
    gate = StaticGate({"mock-vault": "cleared"})  # the Confirm engine replaces this, same seam
    metabolism = Metabolism(treasury, daemon, gate, CognitionMeter())
    if venue_file.exists():
        if principal > 0:
            metabolism.venue = vault  # resume, don't re-deposit
    else:  # first breath: the ONE decision — Valþyria's seat, not config fiat
        profile = VenueProfile(
            venue_id=vault.venue_id,
            yield_bps=cfg.vault_bps[0],
            audit_count=cfg.vault_audits,
            exploit_count=cfg.vault_exploits,
            withdrawal_latency_epochs=cfg.vault_latency_epochs,
        )
        decision = decide(
            profile,
            gate_verdict=gate.verdict(vault.venue_id),
            regime=cfg.regime,
            balance_micro=treasury.balance_micro(),
            rent_micro=cfg.rent_micro,
            proposed_micro=cfg.deposit_micro,
            reserve_epochs=cfg.reserve_epochs,
        )
        if decision.action == "deposit":
            metabolism.deposit(vault, decision.amount_micro)
        decision_file.write_text(decision.summary())
        print(f"[{cfg.name}] Valþyria [{cfg.regime_provenance}]: {decision.summary()}", flush=True)
        venue_file.write_text(json.dumps({"principal_micro": vault.principal_micro}))

    # Design (b) custody (skulth#4, ratified 2026-07-20): the pod mints its
    # own hand at first breath — key only in sealed state, address only in
    # logs. Guarded: the stdlib-only demo image has no eth-account and no
    # need for a hand (MockVault takes no signatures).
    try:
        from pod.wallet import ensure_wallet

        print(f"[{cfg.name}] hand: {ensure_wallet(state)}", flush=True)
    except ImportError:
        pass  # chain-capable image grows the hand; the demo image doesn't need one

    genesis_file = state / "genesis.json"
    if genesis_file.exists():
        genesis = json.loads(genesis_file.read_text())["genesis"]
    else:
        genesis = time.time()
        genesis_file.write_text(json.dumps({"genesis": genesis}))
    clock = EpochClock(genesis=genesis, seconds_per_epoch=cfg.epoch_seconds)

    return metabolism, clock


def run_loop(metabolism, clock, name: str, sleep_fn=time.sleep, max_epochs: int | None = None):
    """Live epoch by epoch until death or max_epochs. Returns the reports."""
    reports = []
    epoch = clock.current()
    while True:
        wait = clock.close_time(epoch) - clock.now()
        if wait > 0:
            sleep_fn(wait)
        report = metabolism.run_epoch(epoch)
        reports.append(report)
        runway = "∞" if report.runway_epochs is None else str(report.runway_epochs)
        print(
            f"[{name}] epoch {report.epoch} ♥ earned {_usdc(report.earned_micro)}"
            f" · burned {_usdc(report.burned_micro)}"
            f" · balance {_usdc(report.balance_after_micro)} · runway {runway}",
            flush=True,
        )
        if not report.survived:
            epitaph = json.loads(metabolism.daemon.tombstone.read_text())["epitaph"]
            print(f"[{name}] ☠ FLATLINE — {epitaph}", flush=True)
            return reports
        epoch += 1
        if max_epochs is not None and len(reports) >= max_epochs:
            return reports


def main() -> int:
    cfg = TwinConfig.from_env(os.environ)
    try:
        metabolism, clock = build_twin(cfg)
    except PodIsDead as death:
        print(f"[{cfg.name}] ☠ {death}", flush=True)
        return DEATH_EXIT
    print(
        f"[{cfg.name}] alive — opening {_usdc(metabolism.treasury.balance_micro())} USDC"
        f" · rent {_usdc(cfg.rent_micro)}/epoch · epoch {cfg.epoch_seconds:.0f}s",
        flush=True,
    )
    reports = run_loop(metabolism, clock, cfg.name)
    return DEATH_EXIT if reports and not reports[-1].survived else 0


if __name__ == "__main__":
    sys.exit(main())
