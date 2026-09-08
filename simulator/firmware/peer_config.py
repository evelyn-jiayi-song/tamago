"""Shared two-board ESP-NOW configuration.

The same file is uploaded to both boards. The board MAC decides its role, so
the two boards keep identical firmware and settings.
"""

REFERENCE_MAC = bytes((0x24, 0xA1, 0x60, 0x74, 0xEF, 0x58))
ACTUATOR_MAC = bytes((0x24, 0xA1, 0x60, 0x74, 0xF5, 0xC8))
CHANNEL = 6

PEER_AXIS = "roll"
REFERENCE_AMPLITUDE_DEG = 10.0
TRIGGER_AMPLITUDE_DEG = 3.0
PEER_TARGET_FRACTION = 0.50
BASE_RPM = 60.0
BASE_AMPLITUDE_REV = 0.25
PEER_ACCEL_RPM_S = 30.0
PEER_SEND_PERIOD_MS = 100
PEER_STALE_TIMEOUT_MS = 400
PEER_WINDOW_MS = 1500
