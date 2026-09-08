"""Board A adapter: publish filtered moving-weight IMU intensity."""

try:
    from simulator.dual_board.ripple_logic import ReferencePublisher
except ImportError:  # When copied beside ripple_logic.py on an ESP32.
    from ripple_logic import ReferencePublisher


class ReferenceNode:
    """Feed BNO055-shaped samples in and send packets through a transport."""

    def __init__(self, transport, source="A", publish_period_ms=50):
        self.transport = transport
        self.publisher = ReferencePublisher(source, publish_period_ms)

    def on_imu_sample(self, sample, now_ms):
        packet = self.publisher.update(sample, now_ms)
        if packet is not None:
            self.transport.send(packet)
        return packet
