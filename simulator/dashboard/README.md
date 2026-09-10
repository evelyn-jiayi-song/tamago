# Local dashboard

The dashboard is a dependency-light local web app. `server.py` owns the USB
serial connection and `index.html` is the control/visualization deck.

```bash
cd simulator
pip install -r requirements.txt
python dashboard/server.py --port /dev/cu.usbserial-020D143B
```

Open <http://127.0.0.1:8080>. For a UI-only preview:

```bash
python dashboard/server.py --dry-run
```

The bridge sends newline-delimited JSON to the ESP32. A run command looks like:

```json
{"cmd":"run","rpm":60,"distance_rev":1.25,"direction":1}
```

`distance_rev: 0` means continuous motion until a stop command. The browser
does not talk to the USB device directly; only the local Python bridge does.

## Capture and plot a commanded run

The dashboard automatically reconnects to named USB ports when boards are
plugged in. Once the dashboard is running, capture a complete commanded run:

```bash
python3 dashboard/capture_session.py \
  --board both --mode smooth --rpm 10 --accel 10 --distance 0.05 \
  --output results/dual-smooth.json
python3 dashboard/plot_session.py results/dual-smooth.json
```

The capture waits for the selected boards, sends the command, polls until the
motor reports idle, and writes JSON, CSV, angle, speed/position, and IMU-motion
plots. Use `--mode run` for the direct profile or `--mode rock` for a finite
rocking command.

To regenerate the presentation plot from the existing physical logs:

```bash
python3 wired_tests/plot_physical_logs.py
```

For a convenience launcher that discovers up to two currently plugged-in
ESP32 serial devices:

```bash
python3 dashboard/start_usb_dashboard.py --http-port 8090
```

The bridge continues retrying the named ports, so a board can be unplugged and
reconnected without restarting the browser dashboard.

For an egg with an uneven center of mass, use **Balanced rock (brake each
reversal)**. It decelerates to zero at each amplitude boundary, reverses while
stopped, and accelerates into the next half-cycle. This reduces reversal
impulse; it cannot correct a static center-of-mass offset without additional
mechanical balancing or IMU feedback.
