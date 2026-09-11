# Isolated dual-board ripple prototype

This directory is a separate prototype for two ESP32 eggs. It does not
modify `simulator/firmware/`, `simulator/dashboard/`, or
`simulator/wifi_dashboard/`, and it contains no auto-start firmware. The
prototype has not been uploaded and does not issue motor commands.

## Behavior

Board A is the reference/leader. It reads a BNO055 sample from the moving
weight, filters a motion score, and sends a packet over ESP-NOW. Board B is the
actuator/follower. It queues the packet, waits 250 ms, scales intensity to
the configured severity and target fraction, then emits a finite motor
*intent* for a later, explicit motor-driver adapter.

The flow is:

```text
BNO055 sample on A
        │
        ▼
gyro + dynamic acceleration → EMA + hysteresis → ESP-NOW packet
                                                     │
                                                     ▼
                              250 ms delay → intensity / severity mapping
                                                     │
                                                     ▼
                                   rock intent or safe stop on B
```

## Files

| File | Purpose |
|---|---|
| `ripple_logic.py` | Pure, host-testable filter, packet publisher, follower controller |
| `espnow_transport.py` | MicroPython ESP-NOW JSON transport; imports hardware modules only on ESP32 |
| `firmware/reference_node.py` | Board A adapter: IMU sample → transport packet |
| `firmware/follower_node.py` | Board B adapter: transport packet → motor intent, never hardware output |
| `simulate_ripple.py` | Synthetic IMU dry-run; no serial, Wi-Fi, ESP-NOW, or motor access |
| `test_ripple_logic.py` | Eight focused unit tests |

## Packet schema

Packets are UTF-8 JSON objects, versioned by `v`:

```json
{
  "v": 1,
  "kind": "motion",
  "source": "A",
  "seq": 42,
  "t_ms": 2100,
  "intensity": 0.73,
  "active": true,
  "axis": "tilt",
  "features": {
    "gyro_dps": 93.2,
    "dynamic_accel_mps2": 0.41
  }
}
```

`kind` is `motion` while active and `stop` when the filtered signal falls
below the stop threshold. `seq` is strictly increasing and lets B reject old
or replayed packets. `t_ms` is the sender’s monotonic millisecond timestamp;
it is informational because the delay is measured on B’s receipt clock.

## Filtering and intensity definition

The raw 0..1 score is:

```text
gyro_score  = clamp(|gyro| / 90 dps, 0, 1)
accel_score = clamp(| |accel| - 9.80665 m/s² | / 2.5 m/s², 0, 1)
raw_score   = 0.70 × gyro_score + 0.30 × accel_score
```

The score is passed through an exponential moving average with time constant
0.18 s. Hysteresis prevents chatter: motion starts at `0.18` and stops at
`0.10`.

Board A publishes at most every 50 ms and sends a transition packet
immediately when active state changes. Board B accepts only packets from its
configured source and only newer sequence numbers.

## Delay, scaling, and output mapping

Defaults are intentionally conservative prototype values:

| Parameter | Default |
|---|---:|
| follower delay | 250 ms |
| target fraction | 0.50 |
| follower base RPM | 100 RPM |
| follower base acceleration | 50 RPM/s |
| peer severity gain | 1.5× |
| peer base amplitude | 3.00 rev |
| follower maximum RPM | 200 RPM |
| follower maximum acceleration | 100 RPM/s |
| minimum effective intensity | 0.20 |
| stale-peer timeout | 1000 ms |

For a valid motion packet:

```text
effective_intensity = clamp(source_intensity × 3.0 × 0.50 × 1.5, 0, 1)
target_rpm          = min(200, 100 × 1.5 × effective_intensity)
amplitude_rev       = 3.00 × effective_intensity
accel               = min(100, 50 × 1.5 × effective_intensity)
cycles               = 2
```

The resulting dictionary is a proposed `rock` intent. It is not sent to a
TMC2209 by this prototype. An eventual adapter must apply its own validated
motor limits and require a physical enable/stop policy.

## Timeout and safe stop

Every accepted packet refreshes B’s peer age. If B receives no valid packet for
more than 1000 ms while a ripple is active, `FollowerController.tick()` emits
exactly one `{"cmd": "stop", "reason": "peer_stale"}` transition. A received
`stop` packet is delayed by the same 250 ms and produces
`reason: "peer_stop"`. The eventual hardware adapter must translate either
stop intent to disable/stop and should also retain a local independent
watchdog and physical power cutoff.

## ESP-NOW configuration

The transport expects a peer MAC and channel. The previously observed board
context was:

```text
reference A: 24:A1:60:74:EF:58
actuator  B: 24:A1:60:74:F5:C8
channel:   6
```

Treat these as configuration inputs to verify read-only immediately before a
future hardware trial. ESP-NOW peers must use the same radio channel. If the
boards are also associated with an access point, that AP’s channel must be
compatible with the ESP-NOW channel.

## Verification without hardware

From the repository root:

```bash
python3 -m unittest simulator.dual_board.test_ripple_logic -v
python3 simulator/dual_board/simulate_ripple.py --duration 4 --step-ms 50
python3 simulator/dual_board/simulate_ripple.py --duration 4 --step-ms 50 --drop-after-ms 1800
```

Expected evidence:

- unit tests: `Ran 8 tests ... OK`
- normal dry-run: an A→B stream, a 250 ms observed ripple delay, and rock/stop intents
- dropped-packet dry-run: `stop` with `reason: 'peer_stale'`

No command in these tests opens a port, imports `machine`, starts ESP-NOW, or
drives a motor.

## Future hardware sequence (not performed here)

1. Read-only verify each board’s MAC, MicroPython version, BNO055 I²C scan,
   TMC wiring, current limit, and a physical power cutoff.
2. Run the dry-run tests again after any parameter change.
3. Integrate the adapters with the existing board loops in a new firmware
   image, retaining a local motor watchdog and requiring an explicit operator
   enable.
4. Test with the motor mechanically unloaded at the lowest validated limit,
   then verify stop and stale-peer behavior before attaching the weight.

This sequence is intentionally not executed by this prototype.
