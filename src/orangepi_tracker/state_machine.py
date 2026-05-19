from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import StateMachineConfig


class TrackingState(str, Enum):
    IDLE = "IDLE"
    TRACKING = "TRACKING"
    LOST_SHORT = "LOST_SHORT"
    SEARCH = "SEARCH"


@dataclass
class TrackingStateMachine:
    config: StateMachineConfig
    state: TrackingState = TrackingState.IDLE
    found_streak: int = 0
    lost_streak: int = 0
    lost_started_at: float | None = None

    def update(self, found: bool, now: float) -> TrackingState:
        if found:
            self.found_streak += 1
            self.lost_streak = 0
            self.lost_started_at = None
            if self.found_streak >= self.config.lock_frames:
                self.state = TrackingState.TRACKING
            return self.state

        self.found_streak = 0
        self.lost_streak += 1
        if self.lost_started_at is None:
            self.lost_started_at = now

        if self.lost_streak >= self.config.lost_frames:
            self.state = TrackingState.LOST_SHORT
        if self.lost_started_at is not None and now - self.lost_started_at >= self.config.search_after_seconds:
            self.state = TrackingState.SEARCH
        return self.state

