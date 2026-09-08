"""Deterministic model for a distance-delayed, damped egg ripple."""

from dataclasses import dataclass
from math import isfinite


def clamp(value, low, high):
    return max(low, min(high, float(value)))


@dataclass
class EggState:
    row: int
    col: int
    amplitude: float = 0.0
    started_ms: float = -1.0
    active_until_ms: float = -1.0
    push_count: int = 0


class RippleSimulation:
    """A small event-based model suitable for deterministic tests and a UI."""

    def __init__(self, size=5, propagation_speed=4.0, damping=0.72,
                 wobble_duration_ms=900):
        if size < 1 or propagation_speed <= 0 or not 0 <= damping <= 1:
            raise ValueError("invalid ripple configuration")
        self.size = int(size)
        self.propagation_speed = float(propagation_speed)
        self.damping = float(damping)
        self.wobble_duration_ms = float(wobble_duration_ms)
        self._events = []
        self._event_order = 0
        self.reset()

    def reset(self):
        self.time_ms = 0.0
        self._events = []
        self._event_order = 0
        self.eggs = [
            EggState(row, col)
            for row in range(self.size)
            for col in range(self.size)
        ]

    def index(self, row, col):
        if not (0 <= row < self.size and 0 <= col < self.size):
            raise IndexError("egg coordinate outside grid")
        return row * self.size + col

    def coordinates(self, index):
        if not 0 <= index < self.size * self.size:
            raise IndexError("egg index outside grid")
        return divmod(index, self.size)

    def neighbors(self, row, col):
        """Return orthogonal neighbors, in stable order, for one egg."""
        candidates = ((row - 1, col), (row, col + 1),
                      (row + 1, col), (row, col - 1))
        return [point for point in candidates
                if 0 <= point[0] < self.size and 0 <= point[1] < self.size]

    def push(self, row, col, strength=1.0, now_ms=None):
        """Schedule a push and its ripple arrival at every egg."""
        strength = clamp(strength, 0.0, 1.0)
        if not isfinite(strength):
            raise ValueError("strength must be finite")
        if now_ms is None:
            now_ms = self.time_ms
        now_ms = float(now_ms)
        self.time_ms = max(self.time_ms, now_ms)
        for target_row in range(self.size):
            for target_col in range(self.size):
                distance = abs(target_row - row) + abs(target_col - col)
                arrival_ms = now_ms + (distance / self.propagation_speed) * 1000.0
                amplitude = strength * (self.damping ** distance)
                self._event_order += 1
                self._events.append((arrival_ms, self._event_order,
                                     target_row, target_col, amplitude))
        self._events.sort(key=lambda event: (event[0], event[1]))

    def advance(self, now_ms):
        """Advance time and apply all ripple arrivals due by ``now_ms``."""
        now_ms = max(self.time_ms, float(now_ms))
        self.time_ms = now_ms
        while self._events and self._events[0][0] <= now_ms:
            arrival_ms, _order, row, col, amplitude = self._events.pop(0)
            state = self.eggs[self.index(row, col)]
            state.amplitude = max(state.amplitude, amplitude)
            state.started_ms = arrival_ms
            state.active_until_ms = arrival_ms + self.wobble_duration_ms
            state.push_count += 1

    def snapshot(self):
        """Return JSON-friendly state for a renderer or test harness."""
        return [
            {
                "row": egg.row,
                "col": egg.col,
                "amplitude": egg.amplitude if egg.active_until_ms >= self.time_ms else 0.0,
                "started_ms": egg.started_ms,
                "active": egg.active_until_ms >= self.time_ms,
                "push_count": egg.push_count,
            }
            for egg in self.eggs
        ]
