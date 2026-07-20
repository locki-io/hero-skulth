"""One clock for the whole pod.

Accelerated calendars desync the moment two organs keep their own time
(skulth#4 P1). Every "what epoch is it?" goes through EpochClock; nothing
else may read the wall clock.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class EpochClock:
    """Maps wall time onto billing epochs.

    genesis: unix seconds at which epoch 0 opened.
    seconds_per_epoch: 3600.0 = one billing day per hour (demo acceleration).
    now: injectable time source — tests pass a fake; production omits it.
    """

    genesis: float
    seconds_per_epoch: float
    now: Callable[[], float] = field(default=time.time)

    def __post_init__(self) -> None:
        if self.seconds_per_epoch <= 0:
            raise ValueError("seconds_per_epoch must be positive")

    def current(self) -> int:
        elapsed = self.now() - self.genesis
        if elapsed < 0:
            raise ValueError("clock precedes genesis")
        return int(elapsed // self.seconds_per_epoch)

    def close_time(self, epoch: int) -> float:
        """Unix seconds at which the given epoch closes (rent judgment moment)."""
        return self.genesis + (epoch + 1) * self.seconds_per_epoch
