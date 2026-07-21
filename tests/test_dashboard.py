"""Face harness — the pure readers proven without any UI import.
The dead twin's view keeps its epitaph; the unborn twin has a designed
empty state; the hero metric knows its moods.
"""

from pod.dashboard import (
    TwinView,
    abstention_marks,
    heartbeat_line,
    read_twin,
    runway_stage,
    survival_principal_micro,
)
from pod.epoch import EpochClock
from pod.twin import build_twin, run_loop
from tests.test_twin import cfg, fake_time


def lived_state(tmp_path, **over):
    max_epochs = over.pop("max_epochs", None)
    config = cfg(tmp_path, **over)
    metabolism, _ = build_twin(config)
    t, now, sleep = fake_time()
    clock = EpochClock(genesis=0.0, seconds_per_epoch=config.epoch_seconds, now=now)
    run_loop(metabolism, clock, config.name, sleep_fn=sleep, max_epochs=max_epochs)
    return tmp_path


def test_unborn_twin_has_designed_empty_state(tmp_path):
    view = read_twin(tmp_path, "twin-x")
    assert view.born is False and view.dead is False
    assert heartbeat_line(view) == "·" * 24


def test_dead_twin_keeps_its_epitaph(tmp_path):
    lived_state(tmp_path)  # starves at epoch 3
    view = read_twin(tmp_path, "twin-b")
    assert view.dead is True
    assert "rent unpaid" in view.epitaph
    assert view.balance_micro == 0
    assert heartbeat_line(view).endswith("─")  # the flatline is drawn
    assert "☠" in heartbeat_line(view)


def test_living_twin_reports_runway_and_beats(tmp_path):
    lived_state(tmp_path, opening_micro=100_000_000, deposit_micro=90_000_000, max_epochs=4)
    view = read_twin(tmp_path, "twin-a")
    assert view.dead is False
    assert view.runway_epochs is not None and view.runway_epochs >= 4
    assert heartbeat_line(view).count("♥") == 4
    assert view.decision.startswith("deposited")


def test_abstention_is_visible(tmp_path):
    lived_state(tmp_path)  # abstained all life
    view = read_twin(tmp_path, "twin-b")
    assert abstention_marks(view) == "▣▣▣"  # three survived epochs, no earnings


def test_torn_ledger_line_is_skipped_not_fatal(tmp_path):
    # a hard host stop can leave a NUL-torn append; the face reads past the scar
    lived_state(tmp_path)
    before = read_twin(tmp_path, "twin-b")
    activity = tmp_path / "pod-activity.jsonl"
    with activity.open("ab") as f:
        f.write(b"\x00" * 483 + b"\n")
    view = read_twin(tmp_path, "twin-b")
    assert view.dead is True
    assert len(view.reports) == len(before.reports)  # the scar cost nothing but itself


def test_runway_moods():
    assert runway_stage(10) == "calm"
    assert runway_stage(4) == "calm"
    assert runway_stage(3) == "amber"
    assert runway_stage(2) == "amber"
    assert runway_stage(1) == "critical"
    assert runway_stage(0) == "critical"
    assert runway_stage(None) == "calm"


def test_survival_principal_honesty_math():
    # $5/mo server ≈ 6849 micro per hour-epoch → at 5% APR needs ≈ $1,200
    needed = survival_principal_micro(rent_micro=6_849, epoch_seconds=3600.0, apr_bps=500)
    assert 1_150_000_000 < needed < 1_250_000_000


def test_dead_view_is_immutable_shape():
    view = TwinView("x", True, True, (), 0, 0, "abstained", "epoch 3: rent unpaid")
    assert view.dead and view.epitaph
