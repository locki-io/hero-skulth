"""Twin-runner harness — whole lives simulated with an injected clock;
no wall-time, no containers, same organs the compose file will run.
"""

import json

import pytest

from pod.death import PodIsDead
from pod.epoch import EpochClock
from pod.twin import TwinConfig, build_twin, run_loop


def cfg(tmp_path, **over):
    base = dict(
        name="t",
        opening_micro=7_200_000,
        deposit_micro=0,
        vault_bps=[300],
        vault_audits=3,
        vault_exploits=0,
        vault_latency_epochs=0,
        rent_micro=2_400_000,
        epoch_seconds=10.0,
        reserve_epochs=3,
        regime="neutral",
        regime_provenance="test",
        state_dir=tmp_path,
    )
    base.update(over)
    return TwinConfig(**base)


def fake_time():
    t = {"now": 0.0}
    return t, (lambda: t["now"]), (lambda s: t.__setitem__("now", t["now"] + s))


def simulate(config, max_epochs=None):
    metabolism, _ = build_twin(config)
    t, now, sleep = fake_time()
    clock = EpochClock(genesis=0.0, seconds_per_epoch=config.epoch_seconds, now=now)
    return run_loop(metabolism, clock, config.name, sleep_fn=sleep, max_epochs=max_epochs)


def test_config_from_env_parses_schedule_and_defaults(tmp_path):
    c = TwinConfig.from_env(
        {
            "SKULTH_POD_NAME": "twin-a",
            "SKULTH_POD_OPENING_MICRO": "100000000",
            "SKULTH_POD_DEPOSIT_MICRO": "90000000",
            "SKULTH_POD_VAULT_BPS": "180,140,90",
            "SKULTH_POD_STATE_DIR": str(tmp_path),
        }
    )
    assert c.vault_bps == [180, 140, 90]
    assert c.rent_micro == 2_400_000  # default
    assert c.epoch_seconds == 3600.0  # default


def test_starved_twin_dies_on_schedule(tmp_path):
    reports = simulate(cfg(tmp_path))
    assert [r.survived for r in reports] == [True, True, True, False]
    record = json.loads((tmp_path / "TOMBSTONE.json").read_text())
    assert record["last_decision"].startswith("abstained")
    assert "doubt is an asset" in record["last_decision"]


def test_funded_twin_survives(tmp_path):
    reports = simulate(
        cfg(tmp_path, opening_micro=100_000_000, deposit_micro=90_000_000),
        max_epochs=6,
    )
    assert len(reports) == 6 and all(r.survived for r in reports)


def test_restart_resumes_without_double_deposit(tmp_path):
    config = cfg(tmp_path, opening_micro=100_000_000, deposit_micro=90_000_000)
    simulate(config, max_epochs=2)
    # "container restart": rebuild from the same state dir
    metabolism, _ = build_twin(config)
    assert metabolism.venue is not None
    assert metabolism.venue.principal_micro == 90_000_000  # restored, not re-deposited
    assert metabolism.treasury.balance_micro() < 100_000_000  # life so far persisted


def test_corpse_refuses_rebuild(tmp_path):
    config = cfg(tmp_path)
    simulate(config)  # dies at epoch 3
    with pytest.raises(PodIsDead):
        build_twin(config)
