# Wi-Fi dashboard (separate experiment)

This folder is intentionally separate from the working USB dashboard. It
uses normal Wi-Fi for laptop communication:

```text
ESP32 HTTP API  <──── Wi-Fi ────>  laptop proxy/dashboard
```

The ESP32 exposes:

- `GET /api/state` for IMU and motor telemetry
- `POST /api/command` for motion commands
- `POST /api/heartbeat` for the motor safety watchdog

The motor stops when a r
unning board has not received a heartbeat for 750 ms.

## Configure each ESP32

On each board, create `firmware/wifi_secrets.py` with the same laptop Wi-Fi
credentials:

```python
WIFI_SSID = "your-network-name"
WIFI_PASSWORD = "your-network-password"
```

Upload `wifi_dashboard/firmware/main.py` and the maintained `firmware/bno055.py`
driver to both boards. Start with motor power disconnected, and record the IP
printed by each board. Both ESP32s and the laptop must be on the same 2.4 GHz
network.

## Start the laptop dashboard

After both ESP32s print their IP addresses, run:

```bash
python3 wifi_dashboard/server.py \
  --esp32-ip egg-a=192.168.1.123 \
  --esp32-ip egg-b=192.168.1.124
```

Open <http://127.0.0.1:8090>.

The dashboard shows both IMU streams and routes commands to the selected egg.
Enable **Peer mode** in the dashboard only after both boards are visible. The
laptop then applies the existing peer-mode behavior: filtered motion from one
egg reaches the other after 250 ms at 50% intensity. Disable peer mode before
changing wiring or testing a motor mechanically.

For a single-board check, one `--esp32-ip` is still supported. Bare addresses
are named `egg1`, `egg2`, and so on.

The current USB dashboard remains at <http://127.0.0.1:8080> and is not
changed by this experiment.
