"""The face — Niove's P4 organ (skulth#4; canon in the niove-helper leaf).

Canon enforced here, not just admired: RUNWAY IS THE HERO (biggest element,
color shifts calm → amber → critical) · NEVER CLEAR THE CORPSE (a dead twin's
panel persists, flatline and epitaph on screen for the rest of the demo) ·
ABSTENTION RENDERED AS DECISION (▣ marks and the reasoning line, never
emptiness) · BROKEN LOOKS INTENTIONAL (designed empty states) · engineering
names outward. Palette: wireframe green on black-purple, magenta glow —
the Hero-skulth card and this screen must rhyme.

Pure state-readers live at the top and are tested without any UI import;
streamlit is touched only inside render(). Read-only by construction —
the face observes the twins' sealed state, it never reaches into a life.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pod.death import ACTIVITY_NAME, TOMBSTONE_NAME

# --- palette (the card's colors — see niove-helper) -------------------------
INK_BG = "#0d0221"
WIRE_GREEN = "#39ff6a"
GLOW_MAGENTA = "#d94fd9"
AMBER = "#ffb347"
CRITICAL = "#ff4d6d"


@dataclass(frozen=True)
class TwinView:
    name: str
    born: bool
    dead: bool
    reports: tuple[dict, ...]
    balance_micro: int
    runway_epochs: int | None
    decision: str
    epitaph: str | None


def read_twin(state_dir: Path, name: str) -> TwinView:
    """Everything the face knows, read from the sealed state — never written."""
    state_dir = Path(state_dir)
    treasury_file = state_dir / "treasury.json"
    if not treasury_file.exists():
        return TwinView(name, False, False, (), 0, None, "", None)

    balance = json.loads(treasury_file.read_text())["balance_micro"]

    reports: list[dict] = []
    activity = state_dir / ACTIVITY_NAME
    if activity.exists():
        for line in activity.read_text().splitlines():
            event = json.loads(line)
            if event.get("action") == "epoch-report":
                reports.append(event)

    decision_file = state_dir / "decision.txt"
    decision = decision_file.read_text().strip() if decision_file.exists() else ""

    tombstone = state_dir / TOMBSTONE_NAME
    epitaph = json.loads(tombstone.read_text())["epitaph"] if tombstone.exists() else None

    runway = reports[-1]["runway_epochs"] if reports else None
    return TwinView(name, True, epitaph is not None, tuple(reports), balance, runway, decision, epitaph)


def runway_stage(runway_epochs: int | None) -> str:
    """The hero metric's mood: calm ≥4 · amber 2–3 · critical ≤1."""
    if runway_epochs is None:
        return "calm"
    if runway_epochs >= 4:
        return "calm"
    if runway_epochs >= 2:
        return "amber"
    return "critical"


def heartbeat_line(view: TwinView, width: int = 24) -> str:
    """♥ per survived epoch; the flatline is drawn and KEPT for the dead."""
    if not view.born:
        return "·" * width
    beats = "".join("♥─" if r["survived"] else "☠" for r in view.reports[-width // 2 :])
    if view.dead:
        beats += "─" * max(0, width - len(beats))
    return beats or "─" * width


def abstention_marks(view: TwinView) -> str:
    """▣ per epoch lived without a venue — the visible shape of doubt."""
    return "▣" * sum(1 for r in view.reports if r["earned_micro"] == 0 and r["survived"])


def survival_principal_micro(rent_micro: int, epoch_seconds: float, apr_bps: int) -> int:
    """Njörðr's honesty gauge: principal needed to live on real yield alone.
    survival_principal = yearly_rent / APR."""
    epochs_per_year = 31_536_000 / epoch_seconds
    yearly_rent = rent_micro * epochs_per_year
    return int(yearly_rent * 10_000 / apr_bps)


def _usdc(micro: int) -> str:
    return f"{micro / 1_000_000:.2f}"


# --- render (streamlit only below this line) --------------------------------


def render() -> None:
    import time

    import streamlit as st

    st.set_page_config(page_title="Hero-skulth — the twins", page_icon="💀", layout="wide")
    st.markdown(
        f"""<style>
        .stApp {{ background: {INK_BG}; }}
        .twin-card {{ border: 1px solid {WIRE_GREEN}; border-radius: 8px;
                      padding: 1rem 1.2rem; font-family: monospace; }}
        .twin-dead {{ border-color: {GLOW_MAGENTA}; }}
        .hero {{ font-size: 2.2rem; font-weight: bold; }}
        .calm {{ color: {WIRE_GREEN}; }} .amber {{ color: {AMBER}; }}
        .critical {{ color: {CRITICAL}; animation: pulse 1s infinite; }}
        @keyframes pulse {{ 50% {{ opacity: 0.35; }} }}
        .beat {{ color: {WIRE_GREEN}; font-size: 1.3rem; letter-spacing: 2px; }}
        .flat {{ color: {GLOW_MAGENTA}; }}
        .reason {{ color: #b8b8d0; font-size: 0.85rem; }}
        h1, h2, h3, p, span, div {{ color: #e8e8f0; }}
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown("## 💀 Hero-skulth — *pay the rent or flatline*")

    rent_micro = int(os.environ.get("SKULTH_POD_RENT_MICRO", "2400000"))
    epoch_seconds = float(os.environ.get("SKULTH_POD_EPOCH_SECONDS", "15"))
    apr_bps = int(os.environ.get("SKULTH_POD_ASSUMED_APR_BPS", "500"))

    states = os.environ.get("SKULTH_DASH_STATES", "twin-a:state-a,twin-b:state-b")
    pairs = [entry.split(":", 1) for entry in states.split(",")]

    columns = st.columns(len(pairs))
    for column, (name, path) in zip(columns, pairs):
        view = read_twin(Path(path), name)
        with column:
            dead_class = " twin-dead" if view.dead else ""
            st.markdown(f'<div class="twin-card{dead_class}">', unsafe_allow_html=True)
            title = f"☠ {name} — DEAD" if view.dead else f"♥ {name}"
            st.markdown(f"### {title}")

            if not view.born:
                st.markdown('<p class="reason">awaiting first tick — the epoch opens soon</p>', unsafe_allow_html=True)
            else:
                stage = runway_stage(view.runway_epochs)
                runway_text = "—" if view.runway_epochs is None else str(view.runway_epochs)
                st.markdown(
                    f'<div class="hero {stage}">RUNWAY {runway_text} epochs</div>',
                    unsafe_allow_html=True,
                )
                beat_class = "beat flat" if view.dead else "beat"
                st.markdown(
                    f'<div class="{beat_class}">{heartbeat_line(view)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"treasury **{_usdc(view.balance_micro)} USDC**")
                marks = abstention_marks(view)
                if marks:
                    st.markdown(f"abstained {marks}")
                if view.decision:
                    st.markdown(f'<p class="reason">decision: {view.decision}</p>', unsafe_allow_html=True)
                if view.epitaph:
                    st.markdown(
                        f'<p class="reason" style="color:{GLOW_MAGENTA}">epitaph: {view.epitaph}<br/>'
                        "(the corpse stays on screen — that is the point)</p>",
                        unsafe_allow_html=True,
                    )
            st.markdown("</div>", unsafe_allow_html=True)

    needed = survival_principal_micro(rent_micro, epoch_seconds, apr_bps)
    st.markdown(
        f'<p class="reason">honesty gauge — survival principal at real yield '
        f"({apr_bps / 100:.1f}% APR): <b>{_usdc(needed)} USDC</b> to live on yield alone "
        f"at {_usdc(rent_micro)}/epoch. Testnet simulation; not financial advice.</p>",
        unsafe_allow_html=True,
    )

    time.sleep(2)
    st.rerun()


if __name__ == "__main__":
    render()
