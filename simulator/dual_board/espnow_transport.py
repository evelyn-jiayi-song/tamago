"""MicroPython ESP-NOW transport for the isolated ripple prototype.

This module is inert on a laptop: ``network`` and ``espnow`` are imported only
when ``EspNowTransport`` is instantiated on an ESP32.  It carries JSON UTF-8
packets and does not know how to drive a motor.
"""

try:
    import ujson as json
except ImportError:
    import json


class EspNowTransport:
    """Send packets to one peer and drain packets received from that peer."""

    def __init__(self, peer_mac, channel=6):
        import network
        import espnow

        self.peer_mac = peer_mac
        self.channel = int(channel)
        self.error = ""
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        try:
            sta.config(channel=self.channel)
        except Exception:
            # An associated station may already be pinned to the AP channel.
            pass
        self.radio = espnow.ESPNow()
        try:
            self.radio.config(rxbuf=1024)
        except Exception:
            pass
        self.radio.active(True)
        try:
            self.radio.add_peer(self.peer_mac, channel=self.channel)
        except OSError as exc:
            if "EXIST" not in str(exc).upper():
                raise

    def send(self, packet):
        """Transmit one JSON packet; return True on a successful send call."""
        try:
            payload = json.dumps(packet)
            self.radio.send(self.peer_mac, payload, False)
            return True
        except Exception as exc:
            self.error = repr(exc)
            return False

    def receive(self):
        """Return all valid packets currently queued, oldest first."""
        packets = []
        while True:
            try:
                mac, message = self.radio.recv(0)
            except Exception as exc:
                self.error = repr(exc)
                break
            if mac is None or message is None:
                break
            if mac != self.peer_mac:
                continue
            try:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                packets.append(json.loads(message))
            except Exception:
                continue
        return packets

    def status(self):
        return {
            "enabled": True,
            "peer_mac": ":".join("{:02X}".format(value) for value in self.peer_mac),
            "channel": self.channel,
            "error": self.error,
        }

