"""Small ESP-NOW transport for the two-board wobble controller."""

import time

try:
    import ujson as json
except ImportError:
    import json

import network
import espnow


class PeerLink:
    def __init__(self, local_mac, reference_mac, actuator_mac, channel):
        self.local_mac = local_mac
        self.reference_mac = reference_mac
        self.actuator_mac = actuator_mac
        self.channel = channel
        self.role = "unknown"
        self.peer_mac = None
        self.radio = None
        self.error = ""
        self.last_tx_ms = 0
        self.last_rx_ms = 0
        self.last_rx = None
        self.tx_seq = 0

        if local_mac == reference_mac:
            self.role = "reference"
            self.peer_mac = actuator_mac
        elif local_mac == actuator_mac:
            self.role = "actuator"
            self.peer_mac = reference_mac
        else:
            self.role = "unassigned"
            self.error = "local MAC is not in peer_config.py"
            return

        try:
            sta = network.WLAN(network.STA_IF)
            sta.active(True)
            try:
                sta.config(channel=channel)
            except Exception:
                # A board associated with an AP may already own its channel.
                # The peer registration below will report a channel mismatch.
                pass
            self.radio = espnow.ESPNow()
            try:
                self.radio.config(rxbuf=528)
            except Exception:
                pass
            self.radio.active(True)
            try:
                self.radio.add_peer(self.peer_mac, channel=channel)
            except OSError as exc:
                # Re-running after a soft reset can leave the singleton peer
                # table populated. It is safe to continue in that case.
                if "EXIST" not in str(exc):
                    raise
        except Exception as exc:
            self.error = repr(exc)
            self.radio = None

    @staticmethod
    def _now_ms():
        return time.ticks_ms()

    @staticmethod
    def _mac_text(mac):
        if mac is None:
            return None
        return ":".join("{:02X}".format(value) for value in mac)

    def send(self, payload):
        if self.radio is None or self.peer_mac is None:
            return False
        try:
            data = json.dumps(payload)
            self.radio.send(self.peer_mac, data, False)
            self.last_tx_ms = self._now_ms()
            return True
        except Exception as exc:
            self.error = repr(exc)
            return False

    def receive_latest(self):
        """Drain queued packets and return the newest valid JSON packet."""
        if self.radio is None:
            return None
        latest = None
        while True:
            try:
                mac, message = self.radio.recv(0)
            except Exception as exc:
                self.error = repr(exc)
                return latest
            if mac is None or message is None:
                return latest
            if mac != self.peer_mac:
                continue
            try:
                if isinstance(message, bytes):
                    message = message.decode()
                latest = json.loads(message)
                self.last_rx_ms = self._now_ms()
                self.last_rx = latest
            except Exception:
                continue
        return latest

    def status(self):
        age = None
        if self.last_rx_ms:
            age = time.ticks_diff(self._now_ms(), self.last_rx_ms)
        return {
            "enabled": self.radio is not None,
            "role": self.role,
            "peer_mac": self._mac_text(self.peer_mac),
            "channel": self.channel,
            "last_rx_age_ms": age,
            "last_rx": self.last_rx,
            "error": self.error,
        }
