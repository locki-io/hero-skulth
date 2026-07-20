"""The regime seam — where skulþ's intelligence enters the pod.

Resolution order (fail-safe by construction — network trouble degrades
the decision, it never blocks it):

  1. `SKULTH_POD_REGIME` env override — demo/twin control, explicit
  2. skulþ's authenticated API (X-API-KEY/-SECRET from env, urllib,
     short timeout) — expects a JSON object carrying a `regime` field;
     the situation-code (A–X) → regime bucketing stays server-side or
     arrives in a later calibration pass against config/default.py's
     SITUATION_MAP (flagged in skulth#4 D6 follow-up)
  3. neutral — the honest default, provenance recorded

Stdlib only; the pod never learns skulþ's internals, only the regime word.
"""

from __future__ import annotations

import json
import urllib.request

from pod.valthyria import REGIME_FACTOR

TIMEOUT_SECONDS = 3.0


def resolve_regime(env: dict) -> tuple[str, str]:
    """Returns (regime, provenance). Never raises."""
    override = env.get("SKULTH_POD_REGIME", "").strip()
    if override:
        regime = override if override in REGIME_FACTOR else "neutral"
        return regime, f"env override ({override})"

    url = env.get("SKULTH_API_URL", "").strip()
    key = env.get("SKULTH_API_KEY_POD", "")
    secret = env.get("SKULTH_API_SECRET_POD", "")
    if url and key and secret:
        try:
            request = urllib.request.Request(
                f"{url.rstrip('/')}/api/trend",
                headers={"X-API-KEY": key, "X-API-SECRET": secret},
            )
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                payload = json.load(response)
            regime = payload.get("regime", "")
            if regime in REGIME_FACTOR:
                return regime, "skulþ api"
            return "neutral", "skulþ api — no regime field yet (calibration pending)"
        except Exception as error:  # any failure degrades, never blocks
            return "neutral", f"degraded — skulþ unreachable ({type(error).__name__})"

    return "neutral", "default (no source configured)"
