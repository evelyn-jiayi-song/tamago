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
