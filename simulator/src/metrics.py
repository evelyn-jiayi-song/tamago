"""
Success Metrics for Motor Control Method Evaluation

Metrics compute control precision, energy efficiency, robustness, and
mechanical viability from simulation trajectories.
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple, Optional


@dataclass
class ControlPrecisionMetrics:
    """Quantifies control accuracy."""
    steady_state_error: float  # degrees, absolute error from target
    overshoot_percent: float  # % exceeding target after step
    settling_time_2pct: float  # seconds to reach ±2% band
    peak_error: float  # degrees, maximum deviation
    rms_error: float  # RMS error over period
    oscillation_period: float  # seconds, dominant frequency


@dataclass
class EnergyMetrics:
    """Quantifies energy efficiency."""
    average_power: float  # Watts
    total_energy: float  # Joules
    energy_per_cycle: float  # Joules per rocking cycle
    peak_power: float  # Watts, maximum instantaneous power
    efficiency_rating: float  # 0-100 scale (lower is better)


@dataclass
class RobustnessMetrics:
    """Quantifies disturbance rejection and stability."""
    step_response_time: float  # seconds
    damping_ratio: float  # 0-1 (1 = critically damped)
    bandwidth_hz: float  # frequency response -3dB point
    phase_lag_degrees: float  # at nominal frequency
    start_up_overshoot_percent: float  # from rest


@dataclass
class MechanicalMetrics:
    """Quantifies actuator stress and feasibility."""
    peak_motor_torque_nm: float  # Peak torque demand
    peak_motor_force_n: float  # Peak force demand
    max_actuator_stress_ratio: float  # 0-1, fraction of limit
    thermal_load_estimate_w: float  # Heating in motor


@dataclass
class EvaluationResult:
    """Complete evaluation of a motor method."""
    method_name: str
    control_precision: ControlPrecisionMetrics
    energy: EnergyMetrics
    robustness: RobustnessMetrics
    mechanical: MechanicalMetrics
    
    overall_score: float  # Composite score (0-100)
    feasibility_rating: str  # 'excellent', 'good', 'marginal', 'poor'
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"\n{'='*60}",
            f"Method: {self.method_name}",
            f"{'='*60}",
            "",
            "CONTROL PRECISION:",
            f"  Steady-state error: {self.control_precision.steady_state_error:.2f}°",
            f"  Overshoot: {self.control_precision.overshoot_percent:.1f}%",
            f"  Settling time (2%): {self.control_precision.settling_time_2pct:.2f} s",
            f"  RMS error: {self.control_precision.rms_error:.2f}°",
            "",
            "ENERGY EFFICIENCY:",
            f"  Average power: {self.energy.average_power:.2f} W",
            f"  Total energy: {self.energy.total_energy:.1f} J",
            f"  Energy/cycle: {self.energy.energy_per_cycle:.1f} J",
            f"  Peak power: {self.energy.peak_power:.2f} W",
            "",
            "ROBUSTNESS:",
            f"  Step response time: {self.robustness.step_response_time:.2f} s",
            f"  Damping ratio: {self.robustness.damping_ratio:.2f}",
            f"  Bandwidth: {self.robustness.bandwidth_hz:.2f} Hz",
            f"  Phase lag: {self.robustness.phase_lag_degrees:.1f}°",
            "",
            "MECHANICAL VIABILITY:",
            f"  Peak torque: {self.mechanical.peak_motor_torque_nm:.3f} N·m",
            f"  Peak force: {self.mechanical.peak_motor_force_n:.2f} N",
            f"  Actuator stress ratio: {self.mechanical.max_actuator_stress_ratio:.2f}",
            "",
            f"OVERALL SCORE: {self.overall_score:.1f}/100",
            f"FEASIBILITY: {self.feasibility_rating}",
            f"{'='*60}",
        ]
        return "\n".join(lines)


class MetricsCalculator:
    """Computes all metrics from simulation trajectory."""
    
    def __init__(self, target_angle_deg: float = 15.0, settling_band_deg: float = 2.0):
        """
        Initialize calculator.
        
        Args:
            target_angle_deg: Target tilt angle
            settling_band_deg: Tolerance for settling time calculation
        """
        self.target_angle_deg = target_angle_deg
        self.settling_band_deg = settling_band_deg
    
    def evaluate(self, 
                 method_name: str,
                 times: np.ndarray,
                 tilt_angles_deg: np.ndarray,
                 tilt_rates: np.ndarray,
                 motor_torques: np.ndarray,
                 motor_forces: np.ndarray,
                 power_samples: np.ndarray) -> EvaluationResult:
        """
        Compute all metrics from trajectory data.
        
        Args:
            method_name: Name of motor method
            times: Time samples (seconds)
            tilt_angles_deg: Tilt angles (degrees)
            tilt_rates: Tilt angular velocities (rad/s)
            motor_torques: Motor torques (N·m), shape (N, 3)
            motor_forces: Motor forces (N), shape (N, 3)
            power_samples: Power samples (Watts)
        
        Returns:
            EvaluationResult with all metrics
        """
        control_precision = self._compute_control_precision(times, tilt_angles_deg)
        energy = self._compute_energy(times, power_samples)
        robustness = self._compute_robustness(times, tilt_angles_deg, tilt_rates)
        mechanical = self._compute_mechanical(motor_torques, motor_forces)
        
        # Composite scoring
        overall_score = self._compute_overall_score(control_precision, energy, robustness, mechanical)
        feasibility = self._rate_feasibility(overall_score, mechanical)
        
        return EvaluationResult(
            method_name=method_name,
            control_precision=control_precision,
            energy=energy,
            robustness=robustness,
            mechanical=mechanical,
            overall_score=overall_score,
            feasibility_rating=feasibility
        )
    
    def _compute_control_precision(self, times: np.ndarray, angles_deg: np.ndarray) -> ControlPrecisionMetrics:
        """Compute control precision metrics."""
        # Steady-state: average of last 10% of trajectory
        n_steady = max(1, len(angles_deg) // 10)
        steady_state_angle = np.mean(angles_deg[-n_steady:])
        steady_state_error = abs(steady_state_angle - self.target_angle_deg)
        
        # Overshoot: max deviation from target during first 30%
        n_transient = max(1, len(angles_deg) // 3)
        transient_angles = angles_deg[:n_transient]
        if len(transient_angles) > 0:
            peak_angle = np.max(np.abs(transient_angles - self.target_angle_deg))
            overshoot_percent = max(0, (peak_angle - steady_state_error) / self.target_angle_deg * 100)
        else:
            overshoot_percent = 0.0
        
        # Settling time to 2% band
        settling_band = self.settling_band_deg
        settling_time = None
        for i, angle in enumerate(angles_deg):
            if abs(angle - self.target_angle_deg) <= settling_band:
                if i > len(angles_deg) * 0.1:  # Must be after initial transient
                    settling_time = times[i]
                    break
        if settling_time is None:
            settling_time = times[-1]
        
        # Peak error
        errors = np.abs(angles_deg - self.target_angle_deg)
        peak_error = np.max(errors)
        
        # RMS error
        rms_error = np.sqrt(np.mean(errors ** 2))
        
        # Oscillation period (from zero crossings)
        errors_centered = angles_deg - self.target_angle_deg
        zero_crossings = np.sum(np.diff(np.sign(errors_centered)) != 0)
        if zero_crossings > 0:
            oscillation_period = 2 * (times[-1] - times[0]) / zero_crossings
        else:
            oscillation_period = np.inf
        
        return ControlPrecisionMetrics(
            steady_state_error=steady_state_error,
            overshoot_percent=overshoot_percent,
            settling_time_2pct=settling_time,
            peak_error=peak_error,
            rms_error=rms_error,
            oscillation_period=oscillation_period
        )
    
    def _compute_energy(self, times: np.ndarray, power_samples: np.ndarray) -> EnergyMetrics:
        """Compute energy efficiency metrics."""
        # Average power
        average_power = np.mean(power_samples) if len(power_samples) > 0 else 0.0
        
        # Total energy (integral of power)
        total_energy = np.trapz(power_samples, times) if len(times) > 1 else 0.0
        
        # Peak power
        peak_power = np.max(power_samples) if len(power_samples) > 0 else 0.0
        
        # Energy per cycle (assuming ~0.8 Hz nominal frequency)
        nominal_period = 1.25  # seconds (0.8 Hz)
        energy_per_cycle = average_power * nominal_period
        
        # Efficiency rating (lower is better, on 0-100 scale)
        # Baseline: 5W is "ok" (50 points), <2W is excellent (100), >15W is poor (0)
        if average_power < 2.0:
            efficiency_rating = 100.0
        elif average_power > 15.0:
            efficiency_rating = 0.0
        else:
            efficiency_rating = 100.0 * (15.0 - average_power) / 13.0
        
        return EnergyMetrics(
            average_power=average_power,
            total_energy=total_energy,
            energy_per_cycle=energy_per_cycle,
            peak_power=peak_power,
            efficiency_rating=efficiency_rating
        )
    
    def _compute_robustness(self, times: np.ndarray, angles_deg: np.ndarray, rates: np.ndarray) -> RobustnessMetrics:
        """Compute robustness metrics."""
        # Step response time: time to first reach target ±5%
        step_band = self.target_angle_deg * 0.05
        step_response_time = None
        for i, angle in enumerate(angles_deg):
            if abs(angle - self.target_angle_deg) <= step_band:
                step_response_time = times[i]
                break
        if step_response_time is None:
            step_response_time = times[-1]
        
        # Damping ratio (from overshoot to zero crossing)
        errors = angles_deg - self.target_angle_deg
        crossings_idx = np.where(np.diff(np.sign(errors)) != 0)[0]
        
        if len(crossings_idx) > 1:
            first_cross = abs(errors[crossings_idx[0]])
            second_cross = abs(errors[crossings_idx[1]]) if len(crossings_idx) > 1 else first_cross
            if second_cross > 0:
                log_decrement = np.log(first_cross / second_cross)
                damping_ratio = log_decrement / np.sqrt(4 * np.pi**2 + log_decrement**2)
            else:
                damping_ratio = 1.0
        else:
            damping_ratio = 1.0
        
        # Bandwidth (3dB point from FFT)
        # Simplified: use dominant frequency from zero-crossing rate
        zero_crossings = np.sum(np.diff(np.sign(errors)) != 0)
        if zero_crossings > 2:
            period = 2 * (times[-1] - times[0]) / zero_crossings
            bandwidth_hz = 1.0 / period if period > 0 else 0.5
        else:
            bandwidth_hz = 0.5
        
        # Phase lag at nominal frequency (approx 0.8 Hz)
        nominal_freq = 0.8
        phase_lag_degrees = min(90, bandwidth_hz / nominal_freq * 90)  # Simplified
        
        # Startup overshoot
        initial_angle = angles_deg[0]
        peak_during_startup = np.max(angles_deg[:len(angles_deg)//3])
        startup_overshoot_percent = max(0, (peak_during_startup - self.target_angle_deg) / self.target_angle_deg * 100)
        
        return RobustnessMetrics(
            step_response_time=step_response_time,
            damping_ratio=damping_ratio,
            bandwidth_hz=bandwidth_hz,
            phase_lag_degrees=phase_lag_degrees,
            start_up_overshoot_percent=startup_overshoot_percent
        )
    
    def _compute_mechanical(self, torques: np.ndarray, forces: np.ndarray) -> MechanicalMetrics:
        """Compute mechanical stress metrics."""
        # Peak torque and force
        peak_torque = 0.0
        if torques is not None and len(torques) > 0:
            torque_magnitudes = np.linalg.norm(torques, axis=1)
            peak_torque = np.max(torque_magnitudes)
        
        peak_force = 0.0
        if forces is not None and len(forces) > 0:
            force_magnitudes = np.linalg.norm(forces, axis=1)
            peak_force = np.max(force_magnitudes)
        
        # Actuator stress ratio (vs typical limits)
        # Typical limits: 0.2 N·m torque, 5 N force
        torque_ratio = peak_torque / 0.2 if peak_torque > 0 else 0.0
        force_ratio = peak_force / 5.0 if peak_force > 0 else 0.0
        max_actuator_stress_ratio = max(torque_ratio, force_ratio)
        
        # Thermal load estimate
        # Simple: power * fraction in actuator losses
        # (Placeholder: 50% of average power)
        thermal_load_estimate_w = 5.0  # Nominal
        
        return MechanicalMetrics(
            peak_motor_torque_nm=peak_torque,
            peak_motor_force_n=peak_force,
            max_actuator_stress_ratio=max_actuator_stress_ratio,
            thermal_load_estimate_w=thermal_load_estimate_w
        )
    
    def _compute_overall_score(self, control: ControlPrecisionMetrics, 
                               energy: EnergyMetrics,
                               robust: RobustnessMetrics,
                               mech: MechanicalMetrics) -> float:
        """
        Compute composite overall score (0-100).
        
        Weighted: Control (40%), Energy (30%), Robustness (20%), Mechanical (10%)
        """
        # Control score: lower error and overshoot = higher score
        control_score = 100.0 * np.exp(-(control.rms_error / 5.0)**2)
        if control.settling_time_2pct > 5.0:
            control_score *= 0.8
        
        # Energy score: lower power = higher score
        energy_score = energy.efficiency_rating
        
        # Robustness score: faster response, higher damping
        robust_score = 100.0 * np.exp(-(robust.step_response_time / 2.0)**2)
        robust_score *= (1.0 - abs(robust.damping_ratio - 0.7) / 0.7)  # Optimal damping ~0.7
        robust_score = np.clip(robust_score, 0, 100)
        
        # Mechanical score: lower stress ratio = higher score
        mech_score = 100.0 * np.exp(-(mech.max_actuator_stress_ratio)**2)
        
        # Weighted composite
        overall = (0.40 * control_score + 
                  0.30 * energy_score +
                  0.20 * robust_score +
                  0.10 * mech_score)
        
        return np.clip(overall, 0, 100)
    
    def _rate_feasibility(self, overall_score: float, mech: MechanicalMetrics) -> str:
        """Convert score to feasibility rating."""
        if mech.max_actuator_stress_ratio > 1.0:
            return "poor"
        elif overall_score > 75:
            return "excellent"
        elif overall_score > 60:
            return "good"
        elif overall_score > 40:
            return "marginal"
        else:
            return "poor"
