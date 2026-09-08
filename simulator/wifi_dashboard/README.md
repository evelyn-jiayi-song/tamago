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

The motor stops when a running board has not received a heartbeat for 750 ms.

## Configure Wi-Fi

Copy `firmware/wifi_secrets.py.example` to `firmware/wifi_secrets.py` and fill
in the network credentials. The real secrets file is ignored by `.gitignore`.

The Wi-Fi firmware is a separate `main.py` copy. Do not upload it over the
working USB firmware until the Wi-Fi path has been tested with the motor
power disconnected.

## Start the laptop dashboard

After the ESP32 prints its IP address, run:

```bash
python3 wifi_dashboard/server.py --esp32-ip 192.168.1.123
```

Open <http://127.0.0.1:8090>.

The current USB dashboard remains at <http://127.0.0.1:8080> and is not
changed by this experiment.
