"""Board B adapter: receive delayed ripple intents without driving hardware."""

try:
    from simulator.dual_board.ripple_logic import FollowerController
except ImportError:  # When copied beside ripple_logic.py on an ESP32.
    from ripple_logic import FollowerController


class FollowerNode:
    """Turn received packets into explicit motor intents for a later adapter.

    ``tick`` returns dictionaries such as ``{"cmd": "rock", ...}`` or
    ``{"cmd": "stop", ...}``.  It never imports ``machine`` and never issues
    a step, enable, or direction signal.
    """

    def __init__(self, transport, source="A", **controller_options):
        self.transport = transport
        self.controller = FollowerController(source, **controller_options)

    def tick(self, now_ms):
        for packet in self.transport.receive():
            self.controller.receive(packet, now_ms)
        return self.controller.tick(now_ms)

    def status(self, now_ms):
        return self.controller.status(now_ms)
