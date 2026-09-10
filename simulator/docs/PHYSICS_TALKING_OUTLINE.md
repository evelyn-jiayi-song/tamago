# Wobble Mechanisms — physics talking outline

## Purpose

Explain how electrical energy becomes an observable wobble:

```text
electrical power
  → stepper magnetic field
  → motor torque
  → planetary gear torque / speed transformation
  → rotating eccentric or offset mass
  → reaction torque on the egg
  → rocking against gravity, contact, and friction
  → heat, sound, vibration, and sensor motion
```

The main teaching strategy is **intuition first, formula second**. The formulas
make the story precise; they are not meant to turn the presentation into a
derivation-heavy lecture.

> **Evidence boundary:** the repository documents the ESP32, TMC2209, stepper,
> IMU, bottom-heavy egg model, and simulation interfaces. A specific planetary
> gear ratio, gear tooth count, eccentric mass, bearing friction, and final
> linkage geometry must be filled in from the manufactured mechanism. Treat
> those values as measured parameters, not assumptions.

---

## Slide 1 — The one-sentence energy story

**Headline:** The egg does not “move because the motor spins”; it moves because
the motor transfers angular momentum into an unbalanced internal mechanism.

Say:

> The battery or USB supply creates current. Current creates magnetic force in
> the stepper. The stepper creates shaft torque. Gears trade speed for torque.
> The geared output moves an offset mass. Because that mass is accelerating
> inside the egg, the egg feels an equal-and-opposite reaction torque and rocks
> against gravity.

Visual:

```text
[electricity] → [motor] → [gears] → [offset mass] → [reaction torque] → [egg wobble]
```

---

## Slide 2 — What is torque?

**Intuition:** Torque is rotational push. A force applied farther from a pivot
has more leverage.

```text
τ = r × F
```

For a perpendicular force:

```text
|τ| = r F
```

Where:

- `τ` is torque in N·m;
- `r` is lever arm in meters;
- `F` is force in newtons.

Use a door analogy:

- push near the hinge: small torque;
- push at the handle: larger torque;
- same force, different lever arm.

Connect to the egg:

- the internal mass is the “hand” applying force;
- the egg’s contact point is the effective pivot;
- the distance from the contact point to the moving mass determines leverage.

---

## Slide 3 — Why the bottom-heavy egg wants to stand up

**Intuition:** Gravity is always trying to lower the center of mass.

When the egg tilts, the center of mass moves sideways relative to the contact
point. Gravity then creates a restoring torque:

```text
τ_gravity = m g d sin(θ)
```

Where:

- `m` is egg mass;
- `g ≈ 9.81 m/s²`;
- `d` is the distance from contact point to center of mass;
- `θ` is tilt angle from upright.

For small angles:

```text
sin(θ) ≈ θ
τ_gravity ≈ m g d θ
```

This looks like a torsional spring:

```text
τ_gravity ≈ k_gravity θ
k_gravity = m g d
```

**Important interpretation:** a larger center-of-mass offset makes the egg more
self-righting, but also requires more actuator torque to hold or excite at the
same tilt.

Repository connection:

- `EggModel.get_restoring_torque_at_angle()`
- `MassDistribution.center_of_mass`
- `create_standard_egg(mass_g=500, com_offset_mm=25)`

---

## Slide 4 — The stepper motor as a torque-producing machine

**Intuition:** The TMC2209 does not “tell the egg where to go.” It energizes
motor coils in a sequence. The rotor aligns with the changing magnetic field.

The controller chain is:

```text
ESP32 command
  → STEP pulse frequency
  → TMC2209 current regulation
  → phase currents in coils A and B
  → magnetic alignment torque
  → rotor angle and shaft motion
```

For the documented motor interface:

```text
200 full steps/rev × 16 microsteps = 3200 commanded steps/rev
```

Step frequency:

```text
f_step = RPM × steps_per_rev / 60
```

At `30 RPM`:

```text
f_step = 30 × 3200 / 60 = 1600 steps/s
```

**Do not overclaim:** microsteps improve command resolution and smoothness, but
they do not guarantee the shaft physically reaches every ideal microstep under
load. Missed steps require an encoder, marker, or video measurement.

---

## Slide 5 — Mechanical energy enters through shaft work

**Intuition:** Torque is the “push”; angle is the “distance traveled” in the
rotational world.

Mechanical work:

```text
W = ∫ τ dθ
```

For approximately constant torque:

```text
W ≈ τ Δθ
```

Mechanical power:

```text
P_mech = τ ω
```

Where angular speed in radians per second is:

```text
ω = 2π × RPM / 60
```

At constant speed, torque determines power. At zero speed, a stepper can
produce holding torque while doing almost no mechanical work; electrical energy
is still dissipated as coil heat.

This distinction is useful when explaining why:

- a stalled motor can become hot;
- a moving motor transfers mechanical energy;
- high RPM and high torque together demand more power.

---

## Slide 6 — What the planetary gear system changes

**Intuition:** Gears are a speed/torque trade. They do not create energy.

For an ideal reduction ratio `N > 1`:

```text
ω_out = ω_motor / N
τ_out = N τ_motor
```

With gearbox efficiency `η_g`:

```text
τ_out ≈ η_g N τ_motor
```

Power approximately follows:

```text
P_out = τ_out ω_out
     ≈ (η_g N τ_motor)(ω_motor / N)
     = η_g P_motor
```

The ratio cancels in the ideal case. The gearbox trades speed for torque; the
efficiency factor accounts for losses.

For a planetary gear train, describe the roles:

- **sun gear:** central input or output;
- **planet gears:** circulate and share load;
- **ring gear:** outer gear;
- **carrier:** holds the planet gears.

The exact ratio depends on which member is fixed and which member is input or
output. Do not present a single planetary ratio until the actual tooth counts
and fixed member are measured.

Generic planetary relationship:

```text
N_s ω_s + N_r ω_r = (N_s + N_r) ω_c
```

Where `N_s` and `N_r` are sun and ring tooth counts, and `ω_s`, `ω_r`, `ω_c`
are sun, ring, and carrier angular velocities.

---

## Slide 7 — Why gears help this egg

The internal mass must accelerate and decelerate repeatedly. The gearbox can
make the motor’s available torque more useful at the mass shaft.

Without reduction:

- higher mass speed;
- lower output torque;
- more abrupt current/load demand;
- potentially less control authority near a heavy or eccentric load.

With reduction:

- lower mass speed;
- higher output torque;
- finer effective control over the mass;
- more time for acceleration and deceleration;
- losses from gear mesh, bearings, and backlash.

**Tradeoff:** reduction improves torque authority but may reduce the maximum
motion frequency and can add backlash, compliance, and noise.

---

## Slide 8 — The rotating offset mass

**Intuition:** A centered flywheel mostly shakes itself. An eccentric mass
creates a rotating force that has a direction.

For an offset mass `m_e` at radius `r` rotating at angular speed `ω`:

```text
F_centripetal = m_e r ω²
```

The internal mechanism must provide this force. The equal-and-opposite reaction
acts on the motor/gearbox/egg assembly.

The direction of the force rotates continuously. Its components can be shown as:

```text
F_x = m_e r ω² cos(φ)
F_y = m_e r ω² sin(φ)
```

where `φ` is the mass phase angle.

If the mass is used to create a rocking moment about the contact point, a simple
lever approximation is:

```text
τ_reaction ≈ F_tangential ℓ
```

where `ℓ` is the effective distance from the contact point to the force line.

**Design insight:** increasing eccentric radius increases available force
linearly, but increasing speed increases force quadratically.

---

## Slide 9 — Angular momentum: why acceleration matters

The rotating mass also carries angular momentum:

```text
L = I ω
```

where `I` is rotational inertia.

Changing that angular momentum requires torque:

```text
τ = dL/dt
```

For approximately constant inertia:

```text
τ ≈ I α
```

where `α` is angular acceleration.

This explains the observed behavior:

- constant-speed rotation can be relatively calm;
- starting, stopping, and reversing the mass creates larger torque demand;
- abrupt reversal injects a sharp impulse into the egg;
- acceleration/deceleration ramps spread the energy transfer over time.

The project’s **Balanced rock** mode deliberately brakes to zero before
reversing, reducing the reversal impulse.

---

## Slide 10 — Gravity, motor torque, and contact friction compete

At any instant, the egg’s angular motion is governed by competing torques:

```text
I_egg θ¨ = τ_motor_reaction
          − τ_gravity
          − τ_contact
          − τ_damping
```

Interpretation:

- `I_egg θ¨`: resistance to changing the egg’s angular motion;
- `τ_motor_reaction`: torque transmitted from the internal mechanism;
- `τ_gravity`: restoring torque toward upright;
- `τ_contact`: torque caused by contact geometry and friction;
- `τ_damping`: energy lost through material, bearing, and air effects.

This is the central “torque budget” slide.

The egg wobbles when the motor periodically supplies enough torque to overcome
losses and perturb the gravitational equilibrium, but not so much that the
contact state becomes unstable.

---

## Slide 11 — Friction: useful, harmful, and easy to misunderstand

### Static friction

Static friction prevents the contact point from sliding:

```text
F_friction ≤ μ_s N
```

If the required tangential force exceeds `μ_s N`, the contact slips.

### Kinetic friction

During sliding:

```text
F_k ≈ μ_k N
```

Usually `μ_k < μ_s`.

### Rolling resistance

Even without visible sliding, deformation and micro-slip consume energy. A simple
model is:

```text
τ_rolling ≈ c_r N
```

where `c_r` is an effective rolling-resistance length.

### Bearing and gear friction

Internal losses can be approximated as:

```text
τ_loss = τ_bearing + τ_mesh + τ_seal + τ_air
```

**Intuitive point:** friction is not just “bad.” Some contact friction helps the
egg grip the table and convert internal forces into rocking. Too much friction
absorbs energy and prevents smooth recovery; too little friction causes slip.

Repository simulation parameters:

- ground friction coefficient: `0.8`;
- rolling friction: `0.001`;
- linear and angular damping: `0.04`.

These are simulation parameters, not measurements of the final surface.

---

## Slide 12 — Energy conversion and losses

Use an energy Sankey diagram:

```text
electrical input
      │
      ├── coil resistance → heat
      ├── driver/regulator losses → heat
      ▼
motor mechanical output
      │
      ├── gear mesh + bearing friction → heat / sound
      ├── air drag and vibration → heat / sound
      ├── contact friction → heat
      ├── gravitational potential energy
      └── egg kinetic energy
```

Energy balance over a time interval:

```text
E_electrical
  = ΔK_motor + ΔK_egg + ΔU_gravity + E_friction
    + E_damping + E_heat + E_unmodeled
```

For a complete steady rocking cycle, the net stored energy may be close to zero:

```text
ΔK + ΔU ≈ 0
```

but the motor must continually replace energy dissipated by friction, damping,
gear losses, and contact losses.

This is why an egg can wobble forever in principle only while power continues
to replenish losses and the controller prevents runaway motion.

---

## Slide 13 — Potential, kinetic, and rotational energy

### Gravitational potential energy

For a small vertical center-of-mass change:

```text
U = m g h
```

As the egg tilts, some input energy is temporarily stored as gravitational
potential energy and then returned as it falls back toward upright.

### Translational kinetic energy

```text
K_translation = 1/2 m v²
```

### Rotational kinetic energy

```text
K_rotation = 1/2 I ω²
```

The moving internal mass can transfer energy into egg rotation, then gravity and
contact return or dissipate part of it. The visible wobble is the result of this
repeated exchange.

**Intuition:** the system behaves less like a one-way conveyor and more like a
poorly damped pendulum that receives small pushes at selected phases.

---

## Slide 14 — Resonance and timing

For the bottom-heavy model, the small-angle natural frequency can be estimated
from effective stiffness and inertia:

```text
ω_n ≈ sqrt(k_gravity / I_egg)
f_n = ω_n / (2π)
```

with:

```text
k_gravity ≈ m g d
```

Driving near a natural frequency can produce a larger wobble for less input
energy, but it also increases sensitivity to:

- mass-distribution error;
- friction changes;
- surface compliance;
- phase error;
- amplitude growth and tipping.

The correct control question is not “How fast can the motor go?” but:

> At what phase and energy level does a small input sustain motion without
> crossing the contact-stability boundary?

---

## Slide 15 — Why uneven mass distribution changes the result

If the center of mass is not aligned with the intended axis:

- `d_CoM` changes with direction;
- restoring torque is different on different sides;
- the same motor command produces different tilt amplitudes;
- friction and contact normal force become asymmetric;
- the egg may show a static lean even when gyro is near zero.

Use a two-parameter picture:

```text
static bias  = equilibrium tilt from mass / geometry
dynamic wobble = time-varying response from motor excitation
```

The IMU can measure the result, but it cannot physically rebalance the mass.
Possible compensation strategies:

1. mechanically shift ballast;
2. identify directional response experimentally;
3. use asymmetric amplitude or acceleration;
4. close the loop on roll/pitch with a safety-limited controller.

---

## Slide 16 — Dashboard concepts as physics instruments

Define the displayed quantities while showing the dashboard:

| Dashboard term | Physical meaning | Unit |
|---|---|---|
| IMU | inertial measurement unit | sensor system |
| Roll / pitch | orientation relative to tare | degrees |
| Gyro | angular velocity | degrees/s |
| Acceleration | specific force; includes gravity | m/s² |
| Dynamic acceleration | `abs(|a| − g)` estimate | m/s² |
| RPM | motor shaft speed | rev/min |
| Step rate | commanded pulse frequency | steps/s |
| Tare | current IMU pose becomes zero | degrees |
| Origin | stored motor shaft reference | commanded steps |
| Tilt limit | controller safety threshold | degrees |

Important distinction:

```text
IMU tare ≠ motor origin
```

Tare changes the orientation reference. Origin changes the motor-position
reference. Neither one proves the physical shaft angle without calibration.

---

## Slide 17 — Connecting formulas to the live dashboard

Use a three-column layout:

| What you see | What it means physically | What to check |
|---|---|---|
| RPM rises | motor angular velocity rises | step frequency and vibration |
| Gyro spikes | egg angular velocity changes quickly | reversal impulse / contact |
| Pitch offset | static mass or mounting bias | center of mass / tare pose |
| Dynamic acceleration rises | non-gravity motion increases | mass excitation / impact |
| Position counter advances | firmware commanded steps | not proof of shaft travel |
| Temperature rises | electrical/mechanical losses | current limit and duty cycle |

Useful paired plots:

- motor RPM vs gyro magnitude;
- motor phase / reversal time vs roll excursion;
- pitch and roll vs direction;
- commanded steps vs measured shaft marker;
- electrical input power vs wobble amplitude.

---

## Slide 18 — Demo narrative

### Demo A: static equilibrium

1. Place the egg upright.
2. Show IMU tare.
3. Tilt it by hand.
4. Release it and explain gravitational restoring torque.

### Demo B: one-way motor motion

1. Run `0.05 rev`.
2. Show `160` commanded steps.
3. Explain that this is software position, not encoder truth.

### Demo C: ordinary versus balanced reversal

1. Run ordinary rocking at conservative RPM.
2. Show gyro spikes around reversals.
3. Run balanced rocking.
4. Show reduced gyro peaks after braking to zero.

### Demo D: energy loss

1. Hold the egg or increase contact friction.
2. Compare amplitude and current/temperature.
3. Explain that more input energy is being consumed by friction and damping.

### Demo E: peer response

1. Egg A moves.
2. Filter extracts motion intensity.
3. Egg B responds after delay and at reduced intensity.
4. Explain that delay is an artistic parameter and a control parameter.

---

## Slide 19 — Measurement plan for the real energy model

To move from qualitative physics to a calibrated model, measure:

### Geometry and mass

- total mass;
- center-of-mass position;
- eccentric mass and radius;
- gear ratio and tooth counts;
- output inertia;
- contact radius.

### Motor and electrical

- coil current;
- motor voltage;
- electrical input power;
- phase resistance;
- torque versus speed;
- driver and motor temperature.

### Mechanical

- shaft angle with encoder or optical marker;
- gearbox backlash;
- bearing drag;
- friction coefficient on actual surface;
- wobble angle and angular velocity;
- missed steps.

### Energy estimate

```text
P_electrical = V_supply I_supply
P_mechanical ≈ τ_output ω_output
η_system = P_useful / P_electrical
```

The useful output must be defined carefully: sustaining wobble amplitude,
raising gravitational potential energy, or producing a target angular motion.

---

## Slide 20 — Final takeaway

**The mechanism is an energy-conversion loop, not a magic wobble source.**

1. The stepper creates controlled torque.
2. The planetary gear system trades speed for torque.
3. The rotating offset mass creates reaction forces and torque.
4. Gravity pulls the egg back toward its stable equilibrium.
5. Friction and damping consume energy.
6. Timing determines whether the egg settles, wobbles, resonates, or tips.
7. The IMU makes the invisible exchange visible.

Closing line:

> The engineering goal is not maximum motion. It is the smallest, best-timed
> transfer of energy that keeps the egg expressive and upright.
