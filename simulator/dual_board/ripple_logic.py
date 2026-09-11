"""Pure control logic for a delayed, scaled two-board ripple effect.

The module is deliberately limited to standard Python operations that are
also available in MicroPython.  It produces *motor intents* as dictionaries;
an integration layer must explicitly translate an intent to a local motor
driver command.
"""

import math


PACKET_VERSION = 1
MOTION_PACKET = "motion"
STOP_PACKET = "stop"

DEFAULT_FILTER_TAU_S = 0.18
DEFAULT_START_THRESHOLD = 0.18
DEFAULT_STOP_THRESHOLD = 0.10
DEFAULT_PUBLISH_PERIOD_MS = 50
DEFAULT_RIPPLE_DELAY_MS = 250
DEFAULT_TARGET_FRACTION = 0.50
DEFAULT_STALE_TIMEOUT_MS = 1000
DEFAULT_BASE_RPM = 100.0
DEFAULT_BASE_AMPLITUDE_REV = 2
DEFAULT_BASE_ACCEL_RPM_S = 50.0
# Peer reactions intentionally use a longer travel than the original manual
# wobble profile. The source constant remains available for non-peer callers.
DEFAULT_PEER_AMPLITUDE_REV = 3.0
DEFAULT_MAX_RPM = 200.0
DEFAULT_MAX_ACCEL_RPM_S = 100.0
DEFAULT_MIN_EFFECTIVE_INTENSITY = 0.2
DEFAULT_SOURCE_RESPONSE_GAIN = 3.0
DEFAULT_PEER_SEVERITY_GAIN = 1.5
DEFAULT_REACTION_SPEED_GAIN = 1.5
DEFAULT_REACTION_ACCEL_GAIN = 1.5
DEFAULT_PEER_CYCLES = 2
DEFAULT_PEER_REACTION_HOLD_MS = 2500
DEFAULT_PEER_STOP_COOLDOWN_MS = 350


def clamp(value, low, high):
    return max(low, min(high, float(value)))


def _number(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(value):
        return float(default)
    return value


def motion_features(imu_sample):
    """Extract gyro magnitude and dynamic acceleration from a BNO055 sample.

    The BNO055 accelerometer includes gravity.  ``dynamic_accel_mps2`` uses
    the deviation of the acceleration magnitude from 1 g, so a still tilted
    board does not look like motion.  Gyro is the primary signal because it
    responds directly to a moving weight.
    """
    gyro = imu_sample.get("gyro", {}) if isinstance(imu_sample, dict) else {}
    accel = imu_sample.get("accel", {}) if isinstance(imu_sample, dict) else {}
    gx = _number(gyro.get("x"))
    gy = _number(gyro.get("y"))
    gz = _number(gyro.get("z"))
    ax = _number(accel.get("x"))
    ay = _number(accel.get("y"))
    az = _number(accel.get("z"))
    gyro_dps = math.sqrt(gx * gx + gy * gy + gz * gz)
    accel_norm = math.sqrt(ax * ax + ay * ay + az * az)
    dynamic_accel_mps2 = abs(accel_norm - 9.80665)
    return {
        "gyro_dps": gyro_dps,
        "dynamic_accel_mps2": dynamic_accel_mps2,
    }


class MotionIntensityFilter:
    """Filter IMU motion into a 0..1 intensity with start/stop hysteresis."""

    def __init__(self, tau_s=DEFAULT_FILTER_TAU_S,
                 start_threshold=DEFAULT_START_THRESHOLD,
                 stop_threshold=DEFAULT_STOP_THRESHOLD):
        if tau_s <= 0:
            raise ValueError("tau_s must be positive")
        if not 0 <= stop_threshold < start_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 <= stop < start <= 1")
        self.tau_s = float(tau_s)
        self.start_threshold = float(start_threshold)
        self.stop_threshold = float(stop_threshold)
        self.intensity = 0.0
        self.active = False
        self.last_features = {"gyro_dps": 0.0, "dynamic_accel_mps2": 0.0}

    def update(self, imu_sample, dt_s):
        """Return ``{raw, intensity, active, features}`` for one IMU sample."""
        dt_s = max(0.0, _number(dt_s))
        features = motion_features(imu_sample)
        # Full-scale values are conservative commissioning values, not sensor
        # limits. They keep ordinary motion in a useful 0..1 control range.
        gyro_score = clamp(features["gyro_dps"] / 90.0, 0.0, 1.0)
        accel_score = clamp(features["dynamic_accel_mps2"] / 2.5, 0.0, 1.0)
        raw = 0.70 * gyro_score + 0.30 * accel_score
        alpha = 1.0 - math.exp(-dt_s / self.tau_s) if dt_s else 0.0
        self.intensity += alpha * (raw - self.intensity)
        if not self.active and self.intensity >= self.start_threshold:
            self.active = True
        elif self.active and self.intensity <= self.stop_threshold:
            self.active = False
        self.last_features = features
        return {
            "raw": raw,
            "intensity": self.intensity,
            "active": self.active,
            "features": dict(features),
        }


def _valid_packet(packet):
    if not isinstance(packet, dict):
        return False
    if packet.get("v") != PACKET_VERSION:
        return False
    if packet.get("kind") not in (MOTION_PACKET, STOP_PACKET):
        return False
    if not isinstance(packet.get("source"), str) or not packet.get("source"):
        return False
    try:
        int(packet.get("seq"))
        float(packet.get("t_ms"))
        intensity = float(packet.get("intensity", 0.0))
    except (TypeError, ValueError):
        return False
    return math.isfinite(intensity) and 0.0 <= intensity <= 1.0


class ReferencePublisher:
    """Board A: turn IMU samples into filtered, rate-limited peer packets."""

    def __init__(self, source="A", publish_period_ms=DEFAULT_PUBLISH_PERIOD_MS,
                 intensity_filter=None):
        self.source = source
        self.publish_period_ms = int(publish_period_ms)
        if self.publish_period_ms <= 0:
            raise ValueError("publish_period_ms must be positive")
        self.filter = intensity_filter or MotionIntensityFilter()
        self.sequence = 0
        self.last_publish_ms = None
        self.last_active = False

    def update(self, imu_sample, now_ms):
        """Return a packet when due, otherwise ``None``."""
        result = self.filter.update(imu_sample, self.publish_period_ms / 1000.0)
        active_changed = result["active"] != self.last_active
        period_due = (self.last_publish_ms is None or
                      now_ms - self.last_publish_ms >= self.publish_period_ms)
        if not active_changed and not period_due:
            return None
        self.sequence += 1
        self.last_publish_ms = int(now_ms)
        self.last_active = result["active"]
        kind = MOTION_PACKET if result["active"] else STOP_PACKET
        return {
            "v": PACKET_VERSION,
            "kind": kind,
            "source": self.source,
            "seq": self.sequence,
            "t_ms": int(now_ms),
            "intensity": round(result["intensity"] if result["active"] else 0.0, 4),
            "active": result["active"],
            "axis": "tilt",
            "features": {
                "gyro_dps": round(result["features"]["gyro_dps"], 3),
                "dynamic_accel_mps2": round(result["features"]["dynamic_accel_mps2"], 3),
            },
        }


class PeerEchoGate:
    """Temporarily suppress a follower's motion from being sent back.

    The board that receives a peer command will also move its body and IMU.
    Without a hold window, that response can be mistaken for a new source
    gesture and create an endless two-board feedback loop.  The gate is a
    transport-side guard; it does not stop the local motor.
    """

    def __init__(self, reaction_hold_ms=DEFAULT_PEER_REACTION_HOLD_MS,
                 stop_cooldown_ms=DEFAULT_PEER_STOP_COOLDOWN_MS):
        self.reaction_hold_ms = int(reaction_hold_ms)
        self.stop_cooldown_ms = int(stop_cooldown_ms)
        if self.reaction_hold_ms <= 0 or self.stop_cooldown_ms < 0:
            raise ValueError("peer gate durations must be positive/non-negative")
        self.suppressed_until_ms = 0
        self.last_reason = "open"

    def trigger(self, now_ms, command):
        """Hold the gate after a peer reaction or its explicit stop."""
        now_ms = int(now_ms)
        command = command if isinstance(command, dict) else {}
        if command.get("cmd") == "rock":
            duration_ms = int(command.get(
                "reaction_hold_ms", self.reaction_hold_ms
            ))
            duration_ms = max(1, duration_ms)
            self.suppressed_until_ms = max(
                self.suppressed_until_ms, now_ms + duration_ms
            )
            self.last_reason = "peer_reaction"
        elif command.get("cmd") == "stop":
            cooldown_ms = int(command.get(
                "stop_cooldown_ms", self.stop_cooldown_ms
            ))
            cooldown_ms = max(0, cooldown_ms)
            self.suppressed_until_ms = max(
                self.suppressed_until_ms, now_ms + cooldown_ms
            )
            self.last_reason = "peer_stop_cooldown"

    def is_suppressed(self, now_ms):
        return int(now_ms) < self.suppressed_until_ms

    def status(self, now_ms):
        now_ms = int(now_ms)
        return {
            "echo_suppressed": self.is_suppressed(now_ms),
            "suppressed_until_ms": self.suppressed_until_ms,
            "remaining_ms": max(0, self.suppressed_until_ms - now_ms),
            "last_reason": self.last_reason,
        }


class FollowerController:
    """Board B: delay, scale, and safety-gate the reference packet stream."""

    def __init__(self, source="A", target_fraction=DEFAULT_TARGET_FRACTION,
                 delay_ms=DEFAULT_RIPPLE_DELAY_MS,
                 stale_timeout_ms=DEFAULT_STALE_TIMEOUT_MS,
                 base_rpm=DEFAULT_BASE_RPM,
                 base_amplitude_rev=DEFAULT_PEER_AMPLITUDE_REV,
                 base_accel_rpm_s=DEFAULT_BASE_ACCEL_RPM_S,
                 max_rpm=DEFAULT_MAX_RPM,
                 max_accel_rpm_s=DEFAULT_MAX_ACCEL_RPM_S,
                 min_effective_intensity=DEFAULT_MIN_EFFECTIVE_INTENSITY,
                 source_response_gain=DEFAULT_SOURCE_RESPONSE_GAIN,
                 peer_severity_gain=DEFAULT_PEER_SEVERITY_GAIN,
                 reaction_speed_gain=DEFAULT_REACTION_SPEED_GAIN,
                 reaction_accel_gain=DEFAULT_REACTION_ACCEL_GAIN,
                 peer_cycles=DEFAULT_PEER_CYCLES,
                 reaction_hold_ms=DEFAULT_PEER_REACTION_HOLD_MS,
                 stop_cooldown_ms=DEFAULT_PEER_STOP_COOLDOWN_MS):
        if not 0 <= target_fraction <= 1:
            raise ValueError("target_fraction must be between 0 and 1")
        if delay_ms < 0 or stale_timeout_ms <= 0:
            raise ValueError("delay_ms must be >= 0 and stale_timeout_ms positive")
        self.source = source
        self.target_fraction = float(target_fraction)
        self.delay_ms = int(delay_ms)
        self.stale_timeout_ms = int(stale_timeout_ms)
        self.base_rpm = float(base_rpm)
        self.base_amplitude_rev = float(base_amplitude_rev)
        self.base_accel_rpm_s = float(base_accel_rpm_s)
        self.max_rpm = float(max_rpm)
        self.max_accel_rpm_s = float(max_accel_rpm_s)
        if self.base_rpm <= 0 or self.base_accel_rpm_s <= 0:
            raise ValueError("base RPM and acceleration must be positive")
        self.min_effective_intensity = float(min_effective_intensity)
        if self.min_effective_intensity < 0:
            raise ValueError("min_effective_intensity must be non-negative")
        if source_response_gain <= 0:
            raise ValueError("source_response_gain must be positive")
        self.source_response_gain = float(source_response_gain)
        if peer_severity_gain <= 0:
            raise ValueError("peer_severity_gain must be positive")
        self.peer_severity_gain = float(peer_severity_gain)
        if reaction_speed_gain <= 0 or reaction_accel_gain <= 0:
            raise ValueError("reaction gains must be positive")
        self.reaction_speed_gain = float(reaction_speed_gain)
        self.reaction_accel_gain = float(reaction_accel_gain)
        self.peer_cycles = int(peer_cycles)
        if self.peer_cycles <= 0:
            raise ValueError("peer_cycles must be positive for finite reactions")
        self.reaction_hold_ms = int(reaction_hold_ms)
        self.stop_cooldown_ms = int(stop_cooldown_ms)
        if self.reaction_hold_ms <= 0 or self.stop_cooldown_ms < 0:
            raise ValueError("peer reaction/stop durations must be positive/non-negative")
        self.pending = []
        self.last_sequence = -1
        self.last_rx_ms = None
        self.last_command = None
        self.last_reason = "waiting_for_peer"

    def receive(self, packet, now_ms):
        """Validate and queue a packet for application after the ripple delay."""
        if not _valid_packet(packet) or packet.get("source") != self.source:
            return False
        sequence = int(packet["seq"])
        if sequence <= self.last_sequence:
            return False
        self.last_sequence = sequence
        self.last_rx_ms = int(now_ms)
        self.pending.append((int(now_ms) + self.delay_ms, packet))
        return True

    @staticmethod
    def _same_command(left, right):
        if left is None or right is None:
            return left == right
        # STOP packets are intentionally published more than once so a
        # delayed follower can recover safely. They are the same motor intent
        # even when the publisher increments the transport sequence number.
        if left.get("cmd") == right.get("cmd") == "stop":
            return left.get("reason") == right.get("reason")
        for key in ("cmd", "source_seq", "reason"):
            if left.get(key) != right.get(key):
                return False
        return (abs(left.get("intensity", 0.0) - right.get("intensity", 0.0)) < 0.005 and
                abs(left.get("rpm", 0.0) - right.get("rpm", 0.0)) < 0.5)

    def _command_for(self, packet):
        source_intensity = clamp(packet.get("intensity", 0.0), 0.0, 1.0)
        # The IMU filter is intentionally conservative, so normal movement
        # often occupies only the lower half of its 0..1 range. Expand that
        # range before applying the user's target fraction; the clamp keeps
        # the follower from exceeding the selected fraction at full motion.
        normalized_source = clamp(
            source_intensity * self.source_response_gain, 0.0, 1.0
        )
        effective = clamp(
            normalized_source * self.target_fraction * self.peer_severity_gain,
            0.0,
            1.0,
        )
        if packet.get("kind") == STOP_PACKET or effective < self.min_effective_intensity:
            return {
                "cmd": "stop",
                "source_seq": int(packet["seq"]),
                "reason": "peer_stop",
                "stop_cooldown_ms": self.stop_cooldown_ms,
            }
        rpm = min(
            self.max_rpm,
            self.base_rpm * self.reaction_speed_gain * effective,
        )
        accel = min(
            self.max_accel_rpm_s,
            self.base_accel_rpm_s * self.reaction_accel_gain * effective,
        )
        amplitude_rev = self.base_amplitude_rev * effective
        # Estimate how long the finite rock needs to ramp and complete its
        # one-cycle travel.  The echo gate uses this to cover the physical
        # reaction, not just the host command latency.
        ramp_s = max(0.0, rpm - 1.0) / max(accel, 1.0)
        travel_s = (
            2.0 * amplitude_rev * self.peer_cycles
            * 60.0 / max(rpm, 1.0)
        )
        reaction_hold_ms = max(
            self.reaction_hold_ms,
            int(round((ramp_s + travel_s + 0.5) * 1000.0)),
        )
        return {
            "cmd": "rock",
            "source_seq": int(packet["seq"]),
            "reason": "peer_motion",
            "intensity": round(effective, 4),
            "rpm": round(rpm, 3),
            "amplitude_rev": round(amplitude_rev, 4),
            "accel": accel,
            "direction": 1,
            "cycles": self.peer_cycles,
            "reaction_hold_ms": reaction_hold_ms,
        }

    def tick(self, now_ms):
        """Return a new motor intent, or ``None`` if no change is required."""
        due = None
        remaining = []
        for due_ms, packet in self.pending:
            if due_ms <= now_ms:
                if due is None or int(packet["seq"]) > int(due["seq"]):
                    due = packet
            else:
                remaining.append((due_ms, packet))
        self.pending = remaining

        if self.last_rx_ms is None:
            command = None
        elif now_ms - self.last_rx_ms > self.stale_timeout_ms:
            command = {
                "cmd": "stop",
                "source_seq": self.last_sequence,
                "reason": "peer_stale",
                "stop_cooldown_ms": self.stop_cooldown_ms,
            }
            self.last_reason = "peer_stale"
        elif due is not None:
            command = self._command_for(due)
            self.last_reason = command.get("reason", "peer_motion")
        else:
            command = None

        if command is None or self._same_command(command, self.last_command):
            return None
        self.last_command = command
        return command

    def status(self, now_ms):
        age = None if self.last_rx_ms is None else max(0, now_ms - self.last_rx_ms)
        return {
            "last_sequence": self.last_sequence,
            "peer_age_ms": age,
            "queued_packets": len(self.pending),
            "last_command": self.last_command,
            "last_reason": self.last_reason,
            "delay_ms": self.delay_ms,
            "target_fraction": self.target_fraction,
            "source_response_gain": self.source_response_gain,
            "peer_severity_gain": self.peer_severity_gain,
            "peer_amplitude_rev": self.base_amplitude_rev,
            "base_rpm": self.base_rpm,
            "base_accel_rpm_s": self.base_accel_rpm_s,
            "reaction_speed_gain": self.reaction_speed_gain,
            "reaction_accel_gain": self.reaction_accel_gain,
            "peer_cycles": self.peer_cycles,
            "reaction_hold_ms": self.reaction_hold_ms,
            "stop_cooldown_ms": self.stop_cooldown_ms,
            "stale_timeout_ms": self.stale_timeout_ms,
        }
