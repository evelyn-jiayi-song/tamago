# Wobble Mechanisms — Canva presentation outline

Use this as the slide-by-slide source for the final presentation. Claims are
marked **Verified**, **Unverified**, or **Design direction** so the deck does
not overstate prototype evidence.

## 1. Title — Wobble Mechanisms

**Message:** A self-righting egg becomes expressive through sensing, internal
motion, and coordination.

Show the two eggs, a motion trail, and the subtitle “From bottom-heavy physics
to coordinated movement.” Mention ESP32, BNO055, TMC2209, stepper motors, and
the laptop dashboard.

## 2. Product concept and user experience

Show idle → initiate → wobble → settle. Explain independent distance motion,
smooth distance motion, finite rocking, continuous rocking, direction reversal,
IMU tare, stop, and immediate stop. Introduce the second egg as a delayed,
lower-intensity response.

**Status:** Commands are implemented in the firmware and dashboard. The final
user experience remains a design direction.

## 3. Project background — why an egg?

Explain the bottom-heavy body and restoring torque:

```text
τgravity = m g dCoM sin(θ)
```

Show geometric center, center of mass, contact point, gravity, and tilt angle.
Connect passive self-righting to active motor excitation.

## 4. Iterations and design-space exploration

Show the progression from mechanism research to hardware:

1. Explore ten actuation architectures.
2. Model egg dynamics and motor methods.
3. Add ESP32 + BNO055 + TMC2209 hardware control.
4. Build USB dashboard and independent board routing.
5. Add peer filtering and delayed follower behavior.
6. Prototype Wi-Fi HTTP transport.
7. Return to USB as the deterministic commissioning path.
8. Add live plots, session capture, and smooth distance motion.

The ten proposed architectures are documented in `MOTOR_CONTROL_PROPOSAL.md`:
eccentric mass, solenoid slider, EAP, hydraulic piston, voice coil, reactive
pendulum, piezo stack, SMA, BLDC cam, and adaptive resonance tracking.

## 5. Current prototype architecture

Use `docs/assets/system-architecture.svg`.

```text
BNO055 → ESP32 MicroPython → TMC2209 STEP/DIR/EN → stepper → mechanism
   ↑                                              ↓
   └──────────── laptop telemetry / commands ─────┘
```

Show separate Egg A and Egg B channels and distinguish command, telemetry, and
optional peer paths.

## 6. Final technical stack

### Embedded

- ESP32 MicroPython
- BNO055-compatible IMU
- TMC2209 STEP/DIR driver
- Four-wire, two-phase stepper motor

### Host

- Python
- local HTML/JavaScript dashboard
- pyserial
- NumPy/SciPy, PyBullet, Trimesh, PyYAML, Matplotlib

### Communications

- USB serial newline-delimited JSON: primary working path
- Wi-Fi HTTP: separate experiment
- ESP-NOW: isolated coordination prototype

## 7. Repository structure

```text
wobble_mechanisms/
├── simulator/src/             physics and egg model
├── simulator/experiments/     simulation benchmarks
├── simulator/firmware/       ESP32 firmware and BNO055 driver
├── simulator/dashboard/      USB bridge, UI, capture, plots
├── simulator/wifi_dashboard/ separate HTTP experiment
├── simulator/dual_board/     peer/ripple logic
├── simulator/wired_tests/     physical logs and characterization
├── simulator/docs/            technical deck, outline, diagrams, assets
├── simulator/datasheet/       motor references
└── prompts/                   engineering-agent prompts
```

Color-code model, firmware, physical tests, coordination, and documentation.

## 8. PCB / electronics slide

Place `docs/assets/egg-unit-sheet1-schematic.svg` prominently. Annotate:

- ESP32 controller
- BNO055 I²C: SDA GPIO 21, SCL GPIO 22
- TMC2209: STEP 25, DIR 26, ENN 27
- separate VMOT motor supply
- regulated ESP32 logic supply
- common ground

State explicitly: the repository contains a schematic/wiring asset, not a
manufactured PCB layout, Gerbers, or verified production board. Present this
as an electronics integration concept.

## 9. Motion primitives and physical units

Compare:

1. **Run:** one-way motion to target distance.
2. **Smooth distance:** one-way motion with pre-target braking.
3. **Rock:** alternating direction at one-way amplitude; finite or continuous.

Explain:

```text
200 full steps/rev × 16 microsteps = 3200 commanded steps/rev
0.05 rev = 160 commanded steps
1.00 rev = 3200 commanded steps
```

Emphasize that software steps are not proof of physical shaft motion without an
encoder or marker.

## 10. Gyro, acceleration, speed, and their effect on rocking

### Gyroscope

Measures angular velocity in degrees/second. High gyro magnitude means the egg
or internal mass is rotating rapidly. It is the primary peer-motion signal.
A stationary but tilted egg can have near-zero gyro.

### Accelerometer

Measures specific force, including gravity. A stationary sensor is near 1 g.
The dynamic-motion estimate is:

```text
dynamic_accel = abs(|accel| − 9.80665 m/s²)
```

This detects movement beyond static gravity.

### Speed / RPM

RPM is motor-shaft speed:

```text
step frequency = RPM × 3200 / 60
```

Higher RPM generally increases motion tempo and inertial excitation. The exact
rock angle depends on mechanism geometry, mass, friction, and resonance.

### Acceleration

Acceleration is the RPM change rate in RPM/s. Higher acceleration produces
sharper changes in momentum and may excite vibration; lower acceleration gives
smoother motion and lower current spikes. Safe loaded limits require testing.

## 11. Smooth-motion visualization

Show normal versus smooth distance:

- normal mode ramps toward cruise RPM and stops at the target;
- smooth mode estimates braking distance and reduces RPM before the endpoint.

Use the live dashboard’s speed/position plot and the capture tools:

```bash
python3 dashboard/capture_session.py --board both --mode smooth \
  --rpm 10 --accel 10 --distance 0.05 \
  --output results/dual-smooth.json
python3 dashboard/plot_session.py results/dual-smooth.json
```

## 12. Coordination algorithm

```text
IMU sample
 → gyro magnitude + dynamic acceleration
 → weighted score
 → EMA smoothing (τ = 0.18 s)
 → hysteresis (start 0.18 / stop 0.10)
 → 250 ms delay
 → follower scaling, default 50%
 → rock intent
```

Score:

```text
gyro_score  = clamp(|gyro| / 90 dps, 0, 1)
accel_score = clamp(dynamic_accel / 2.5, 0, 1)
raw_score   = 0.70 gyro_score + 0.30 accel_score
```

Show source intensity, delayed follower intensity, packet sequence, and stale
timeout. Explain duplicate-rock suppression and independent local controls.

## 13. Live plots and physical validation

Use:

- `docs/assets/physical-validation.svg`
- dashboard wobble-angle history
- dashboard IMU interlink plot
- `wired_tests/plot_physical_logs.py`

The existing physical log records:

- finite 0.05-rev run reached 160 steps;
- one rock cycle reversed and stopped;
- continuous-rock stop latency about 110–113 ms;
- full-circle runs reached ±3200 software steps;
- observed unloaded-board temperature about 31–32 °C.

State clearly that these are unloaded-board/command-path results, not final
loaded-mechanism certification.

## 14. Failed attempts and engineering lessons

### Wi-Fi

The Wi-Fi branch worked after using a compatible hotspot and assigned an IP,
but the original laptop hotspot/security behavior was not reliably compatible
with the ESP32 MicroPython WLAN path. USB became the deterministic route.

The Wi-Fi firmware also has a 750 ms heartbeat watchdog. Running Wi-Fi firmware
through the USB dashboard without Wi-Fi heartbeats caused commands to start and
then stop.

### Power

TMC2209 VDD powers driver logic; it does not power the ESP32. Removing USB can
remove ESP32 power even when motor VMOT remains connected.

### Physical motion

Software position can advance without physical motion if VMOT, ENN, STEP, DIR,
current limit, coil pairing, driver health, or mechanical coupling is wrong.

### IMU

Intermittent BNO055 reads can result from wiring, 3.3 V integrity, EMI, sensor
damage, or address mismatch. Retried reads do not replace electrical testing.

## 15. Validation boundary

Separate three levels:

1. simulation;
2. unloaded board and command-path validation;
3. loaded mechanism and product validation.

The simulator currently uses approximations in parts of the physical model.
The final presentation should not claim simulated rankings as measured product
performance.

## 16. Artistic vision

### Core artistic motivation

The project asks how a machine can feel less like a device and more like a
small character. The egg is familiar, vulnerable, and slightly comic: it has a
recognizable body, a tendency to lose balance, and a visible effort to recover.
That makes tiny changes in timing and posture readable as personality.

### 1. The egg should have personality

Personality comes from consistent movement qualities rather than a face or
voice:

- a cautious egg hesitates and uses small amplitudes;
- a curious egg explores with short, irregular gestures;
- a confident egg uses larger, clearer motions;
- a tired egg slows down and settles more heavily;
- a surprised egg gives a quick impulse, then recovers.

The design question is not “How do we animate an egg?” It is:

> How little movement is needed for a viewer to infer intention?

### 2. Sustained movement matters

A single wobble reads as an event. Sustained movement reads as a state.

The goal is not a one-shot trick where the egg rocks and stops. It is a
maintained, alive-looking behavior that can continue while remaining bounded and
safe:

- energy is replenished continuously rather than only at startup;
- acceleration and deceleration become phrasing;
- damping becomes calm, fatigue, or recovery;
- small variation prevents a loop from feeling mechanically identical;
- a safety controller prevents “forever” from becoming uncontrolled motion.

This creates a distinction between:

- **gesture:** one motion event;
- **behavior:** a sustained pattern;
- **presence:** the feeling that the object remains responsive over time.

### 3. Movement should be interconnected

The eggs should not behave like two copies of the same animation. They should
notice one another and develop a relationship.

Possible relationship vocabulary:

- mirror: answer with a related but not identical motion;
- echo: repeat after a delay;
- interrupt: react while the other is still moving;
- accompany: move with a softer intensity;
- synchronize: temporarily align, then drift apart;
- ignore: remain quiet when the other signal is weak.

The technical peer pipeline supports this artistic goal:

```text
Egg A motion
 → gyro + dynamic acceleration
 → filtered intent
 → intentional delay
 → reduced follower intensity
 → Egg B response
```

The delay is important. Perfect synchronization looks like duplication; a
slightly delayed response looks like listening.

### Artistic thesis

> We are building two small bodies that communicate through motion: each egg
> has a personality, each can sustain a state, and each can change because the
> other one moved.

Frame the eggs as a conversation:

- one initiates;
- one listens;
- one answers with a softer, delayed gesture;
- both settle back toward equilibrium.

Translate engineering parameters into artistic language:

- acceleration = gesture sharpness;
- RPM = tempo;
- amplitude = intensity;
- delay = anticipation;
- damping = calm or fatigue.

Use a playful visual language: two egg silhouettes, staggered motion trails,
small captions such as “listen,” “answer,” “hesitate,” and “settle,” plus
rainbow accents that distinguish each egg without making them feel identical.

## 17. Future steps

Prioritize:

1. Add shaft marker or encoder and measure missed steps.
2. Measure final shell mass, center of mass, inertia, and linkage ratio.
3. Validate independent ESP32 power and TMC current limits.
4. Measure loaded tilt, natural frequency, temperature, and repeatability.
5. Add production PCB design, protection, test points, and strain relief.
6. Mature peer transport only after independent motion is reliable.

## 18. Learning slide — intentionally blank

Title: **What We Learned**

Leave the main area blank for live reflection. Optional footer prompts:

- What surprised us?
- Which assumption failed?
- What became clearer through testing?
- What should the next prototype teach us?

## Appendix — references

- `simulator/docs/TECHNICAL_PRESENTATION.md`
- `simulator/docs/assets/egg-unit-sheet1-schematic.svg`
- `simulator/docs/assets/system-architecture.svg`
- `simulator/docs/assets/physical-validation.svg`
- `simulator/wired_tests/physical_test_log.md`
- `simulator/wired_tests/plot_physical_logs.py`
- `simulator/dashboard/capture_session.py`
- `simulator/dashboard/plot_session.py`
- `simulator/dual_board/README.md`
- `simulator/wifi_dashboard/README.md`
- `simulator/datasheet/SM-17HS4023.pdf`
