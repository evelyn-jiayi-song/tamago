"""
10 Motor Control Methods for Energy-Efficient Egg Rocking

Each method is implemented as a MotorMethod subclass that:
- Accepts tilt angle feedback
- Returns force/torque commands for the simulator
- Calculates power consumption
- Can be tuned with parameters
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from dataclasses import dataclass


class MotorMethod(ABC):
    """Abstract base class for motor control methods."""
    
    def __init__(self, name: str):
        self.name = name
        self.time = 0.0
        self.last_angle = 0.0
        self.power_sum = 0.0
    
    @abstractmethod
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Update motor command based on current tilt angle.
        
        Args:
            tilt_angle: Current tilt angle in radians
            dt: Time step in seconds
        
        Returns:
            (force_vector, torque_vector) where each is 3D np.ndarray or None
        """
        pass
    
    @abstractmethod
    def get_power_consumption(self) -> float:
        """Return current power consumption in Watts."""
        pass
    
    def reset(self):
        """Reset internal state."""
        self.time = 0.0
        self.last_angle = 0.0
        self.power_sum = 0.0


# METHOD 1: Eccentric Mass Spinning
class EccentricMassSpinner(MotorMethod):
    """
    Rotational flywheel with constant or variable speed.
    Gyroscopic effects produce rocking motion.
    """
    
    def __init__(self, rpm: float = 500, mass_offset_mm: float = 30, motor_power_w: float = 3.0):
        super().__init__("Eccentric Mass Spinning")
        self.rpm = rpm
        self.mass_offset_mm = mass_offset_mm
        self.motor_power_w = motor_power_w
        self.phase = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        self.phase += (self.rpm / 60.0) * 2 * np.pi * dt  # rad/s
        
        # Gyroscopic torque from spinning mass
        # Simplified: τ = ω_spin × L, where L is angular momentum
        # For now, approximate as sinusoidal torque at spin frequency
        spin_freq_hz = self.rpm / 60.0
        torque_amplitude = 0.05  # N·m
        torque_y = torque_amplitude * np.sin(self.phase)
        
        torque = np.array([0, torque_y, 0])
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        return self.motor_power_w


# METHOD 2: Linear Solenoid Actuator
class LinearSolenoidSlider(MotorMethod):
    """
    Solenoid-driven mass slider with spring restoring force.
    PID-controlled slider position.
    """
    
    def __init__(self, max_force_n: float = 2.0, damping: float = 0.1, kp: float = 0.5, ki: float = 0.1, kd: float = 0.2):
        super().__init__("Linear Solenoid Slider")
        self.max_force_n = max_force_n
        self.damping = damping
        self.kp = kp
        self.ki = ki
        self.kd = kd
        
        self.slider_pos = 0.0  # mm
        self.slider_vel = 0.0  # mm/s
        self.error_integral = 0.0
        self.last_error = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        
        # PID controller: target slider position based on angle
        target_pos = tilt_angle * 100  # Simple proportional mapping
        error = target_pos - self.slider_pos
        
        self.error_integral += error * dt
        error_rate = (error - self.last_error) / dt if dt > 0 else 0
        
        # PID output
        u = self.kp * error + self.ki * self.error_integral + self.kd * error_rate
        force = np.clip(u, -self.max_force_n, self.max_force_n)
        
        # Simulate slider dynamics
        self.slider_vel += (force - self.damping * self.slider_vel) * dt
        self.slider_pos += self.slider_vel * dt
        
        self.last_error = error
        self.last_angle = tilt_angle
        
        # Apply torque from shifted mass
        torque_y = -(self.slider_pos / 1000.0) * 0.1  # Convert to N·m
        torque = np.array([0, torque_y, 0])
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Power ≈ resistive heating + mechanical work
        abs_current = abs(self.slider_vel) / 100.0  # Simplified current model
        coil_resistance = 5.0  # Ohms
        power = (abs_current ** 2) * coil_resistance + abs(self.slider_vel * 0.01)
        return max(0.1, power)


# METHOD 3: Electroactive Polymer (EAP)
class EAPMuscleActuator(MotorMethod):
    """
    Dielectric elastomer muscle with high-voltage drive.
    Very low power but slow response time.
    """
    
    def __init__(self, frequency_hz: float = 0.5, amplitude: float = 0.05, voltage_v: float = 200):
        super().__init__("EAP Muscle Actuator")
        self.frequency_hz = frequency_hz
        self.amplitude = amplitude
        self.voltage_v = voltage_v
        self.phase = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        self.phase += self.frequency_hz * 2 * np.pi * dt
        
        # EAP contraction produces torque
        # Modulate voltage with feedback for stability
        modulation = 0.8 + 0.2 * np.cos(tilt_angle)  # 0.6-1.0 range
        torque_y = self.amplitude * modulation * np.sin(self.phase)
        
        torque = np.array([0, torque_y, 0])
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Capacitive load: P = C·V²·f
        # Approximate as very low power
        return 1.5


# METHOD 4: Hydraulic Piston Actuator
class HydraulicPistonActuator(MotorMethod):
    """
    Micro hydraulic pump with proportional directional valve.
    Good force output but moderate efficiency.
    """
    
    def __init__(self, max_pressure_bar: float = 100, pump_flow_ml_min: float = 50, damping: float = 0.15):
        super().__init__("Hydraulic Piston")
        self.max_pressure_bar = max_pressure_bar
        self.pump_flow_ml_min = pump_flow_ml_min
        self.damping = damping
        
        self.piston_pos = 0.0
        self.piston_vel = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        
        # Open-loop pump, proportional valve modulation
        valve_cmd = np.sin(self.time * 1.0)  # Slow oscillation
        pump_pressure = self.max_pressure_bar * max(0, valve_cmd)
        piston_force = (pump_pressure * 1e5) / 1e6  # Simplified: bar to N
        
        # Piston dynamics
        self.piston_vel += (piston_force - self.damping * self.piston_vel) * dt
        self.piston_pos += self.piston_vel * dt
        
        # Torque from piston
        torque_y = -(self.piston_pos / 1000.0) * 0.15
        torque = np.array([0, torque_y, 0])
        
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Pump + system losses
        flow_lpm = self.pump_flow_ml_min / 1000.0
        pressure_bar = self.max_pressure_bar * max(0, np.sin(self.time * 1.0))
        power_w = (flow_lpm * pressure_bar) / 600.0  # Approximate hydraulic power
        return 10.0  # Typical value


# METHOD 5: Voice Coil Motor
class VoiceCoilActuator(MotorMethod):
    """
    Linear voice coil (Lorentz force) actuator.
    Smooth, linear response; efficient at moderate frequencies.
    """
    
    def __init__(self, frequency_hz: float = 0.8, amplitude_mm: float = 20, kp: float = 0.3):
        super().__init__("Voice Coil Motor")
        self.frequency_hz = frequency_hz
        self.amplitude_mm = amplitude_mm
        self.kp = kp
        
        self.pos = 0.0
        self.vel = 0.0
        self.phase = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        self.phase += self.frequency_hz * 2 * np.pi * dt
        
        # Target position based on angle feedback
        target_pos = tilt_angle * 50  # mm
        error = target_pos - self.pos
        
        # Voice coil force output (linear F-I relationship)
        force = self.kp * error
        
        # Coil dynamics
        spring_constant = 0.5  # N/mm
        damping = 0.05
        self.vel += (force - spring_constant * self.pos - damping * self.vel) * dt
        self.pos += self.vel * dt
        
        # Torque output
        torque_y = -(self.pos / 1000.0) * 0.08
        torque = np.array([0, torque_y, 0])
        
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Coil heating: I²R + spring energy storage
        return 5.0


# METHOD 6: Reactive Pendulum
class ReactivePendulum(MotorMethod):
    """
    Internal swinging arm/leg producing reaction torque.
    Simple, very reliable.
    """
    
    def __init__(self, arm_length_mm: float = 50, motor_rpm: float = 300, arm_mass_g: float = 50):
        super().__init__("Reactive Pendulum")
        self.arm_length_mm = arm_length_mm
        self.motor_rpm = motor_rpm
        self.arm_mass_g = arm_mass_g
        
        self.arm_angle = 0.0
        self.crank_phase = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        
        # Crank mechanism: simple harmonic motion
        crank_freq = self.motor_rpm / 60.0
        self.crank_phase += crank_freq * 2 * np.pi * dt
        
        # Arm position follows crank
        crank_amplitude = 45  # degrees
        self.arm_angle = crank_amplitude * np.sin(self.crank_phase)
        
        # Reaction torque from arm swing
        # Τ ≈ -I_arm·α ≈ -m·L²·(d²θ/dt²)
        arm_angular_accel = -(crank_amplitude * np.pi / 180) * (2 * np.pi * crank_freq)**2 * np.sin(self.crank_phase)
        arm_inertia = (self.arm_mass_g / 1000) * (self.arm_length_mm / 1000)**2
        
        reaction_torque = -arm_inertia * arm_angular_accel
        torque = np.array([0, reaction_torque, 0])
        
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Motor power
        return 3.5


# METHOD 7: Piezoelectric Stack Array
class PiezoStackArray(MotorMethod):
    """
    Distributed piezo actuators with multiplexed drive.
    Very low power baseline, high precision.
    """
    
    def __init__(self, num_stacks: int = 8, voltage_v: float = 200, frequency_hz: float = 2.0):
        super().__init__("Piezo Stack Array")
        self.num_stacks = num_stacks
        self.voltage_v = voltage_v
        self.frequency_hz = frequency_hz
        self.phase = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        self.phase += self.frequency_hz * 2 * np.pi * dt
        
        # Distributed actuation creates net torque
        # Simplified: sinusoidal voltage drive
        stack_displacement = 0.01 * np.sin(self.phase)  # mm per stack
        
        # Sum distributed forces → net torque
        torque_y = stack_displacement * 0.04
        torque = np.array([0, torque_y, 0])
        
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Very low: P ≈ C·V²·f
        # Approximate: 8 stacks, 200V, 2Hz
        return 1.0


# METHOD 8: Shape-Memory Alloy Spring
class SMASpringActuator(MotorMethod):
    """
    Thermal-cycle driven SMA wire contraction/relaxation.
    Slow but silent and reliable.
    """
    
    def __init__(self, max_contraction_pct: float = 5.0, cycle_period_s: float = 3.0, heating_power_w: float = 8.0):
        super().__init__("SMA Spring Actuator")
        self.max_contraction_pct = max_contraction_pct
        self.cycle_period_s = cycle_period_s
        self.heating_power_w = heating_power_w
        
        self.spring_strain = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        
        # Cycle: heating phase (contraction) / cooling phase (extension)
        cycle_phase = (self.time % self.cycle_period_s) / self.cycle_period_s
        
        if cycle_phase < 0.5:
            # Heating: contract
            self.spring_strain = self.max_contraction_pct * (cycle_phase * 2)
        else:
            # Cooling: extend
            self.spring_strain = self.max_contraction_pct * (2 - cycle_phase * 2)
        
        # Torque from spring force
        torque_y = -(self.spring_strain / 100.0) * 0.06
        torque = np.array([0, torque_y, 0])
        
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Heating phase only
        cycle_phase = (self.time % self.cycle_period_s) / self.cycle_period_s
        if cycle_phase < 0.5:
            return self.heating_power_w
        else:
            return 0.5  # Passive cooling, minimal power


# METHOD 9: BLDC Motor with Cam Follower
class BLDCCamFollower(MotorMethod):
    """
    High-speed brushless motor driving offset cam/crank.
    Efficient, reliable, proven technology.
    """
    
    def __init__(self, motor_rpm: float = 2000, cam_offset_mm: float = 15, motor_efficiency: float = 0.85):
        super().__init__("BLDC Cam Follower")
        self.motor_rpm = motor_rpm
        self.cam_offset_mm = cam_offset_mm
        self.motor_efficiency = motor_efficiency
        
        self.cam_angle = 0.0
        self.mass_pos = 0.0
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        
        # Cam rotation
        motor_freq = self.motor_rpm / 60.0
        self.cam_angle += motor_freq * 2 * np.pi * dt
        
        # Cam-follower linkage: mass position follows sine wave
        self.mass_pos = self.cam_offset_mm * np.sin(self.cam_angle)
        
        # Torque from shifted mass
        torque_y = -(self.mass_pos / 1000.0) * 0.1
        torque = np.array([0, torque_y, 0])
        
        self.last_angle = tilt_angle
        
        return None, torque
    
    def get_power_consumption(self) -> float:
        # Motor input power, accounting for efficiency
        # Estimate: ~5W output → ~6W input at 85% efficiency
        return 6.0


# METHOD 10: Adaptive Resonance Tracking
class AdaptiveResonanceTracker(MotorMethod):
    """
    Frequency-tracking oscillator that continuously estimates
    and drives at the system's resonant frequency.
    """
    
    def __init__(self, estimator_tau_s: float = 5.0, max_amplitude_nm: float = 0.1):
        super().__init__("Adaptive Resonance Tracker")
        self.estimator_tau_s = estimator_tau_s
        self.max_amplitude_nm = max_amplitude_nm
        
        self.estimated_frequency = 0.8  # Hz (initial guess)
        self.estimated_damping = 0.1
        self.phase = 0.0
        self.freq_update_count = 0
        
        self.angle_history = []
        self.time_history = []
    
    def update(self, tilt_angle: float, dt: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        self.time += dt
        
        # Store history for frequency estimation
        self.time_history.append(self.time)
        self.angle_history.append(tilt_angle)
        
        # Periodically update frequency estimate (every ~1 second)
        self.freq_update_count += 1
        if self.freq_update_count > 1000 and len(self.angle_history) > 100:
            self._estimate_frequency()
            self.freq_update_count = 0
        
        # Drive at estimated resonant frequency
        self.phase += self.estimated_frequency * 2 * np.pi * dt
        
        # Amplitude modulation: reduce if already oscillating
        amplitude = self.max_amplitude_nm / (1.0 + abs(tilt_angle) * 2)
        torque_y = amplitude * np.sin(self.phase)
        
        torque = np.array([0, torque_y, 0])
        self.last_angle = tilt_angle
        
        return None, torque
    
    def _estimate_frequency(self):
        """Estimate dominant frequency using simple FFT-like approach."""
        # Simplified: count zero crossings
        if len(self.angle_history) < 50:
            return
        
        recent = np.array(self.angle_history[-100:])
        recent_times = np.array(self.time_history[-100:])
        
        # Zero crossings
        zero_crossings = np.sum(np.diff(np.sign(recent)) != 0)
        if zero_crossings > 2:
            period = 2 * (recent_times[-1] - recent_times[0]) / zero_crossings
            if period > 0.1:
                self.estimated_frequency = 1.0 / period
                self.estimated_frequency = np.clip(self.estimated_frequency, 0.3, 3.0)
    
    def get_power_consumption(self) -> float:
        # Resonant drive is highly efficient
        # Power scales with damping losses
        return 2.0


# Factory function
def create_all_methods() -> list:
    """Create instances of all 10 motor control methods with default parameters."""
    methods = [
        EccentricMassSpinner(rpm=500),
        LinearSolenoidSlider(),
        EAPMuscleActuator(),
        HydraulicPistonActuator(),
        VoiceCoilActuator(),
        ReactivePendulum(),
        PiezoStackArray(),
        SMASpringActuator(),
        BLDCCamFollower(),
        AdaptiveResonanceTracker(),
    ]
    return methods
