"""
PyBullet-based physics engine wrapper for egg-shaped rocking systems.
Encapsulates rigid-body dynamics, contact modeling, and motor actuation.
"""

import numpy as np
import pybullet as p
import pybullet_data
from dataclasses import dataclass
from typing import Tuple, List, Optional
import time


@dataclass
class PhysicsConfig:
    """Global physics simulation parameters."""
    gravity: float = 9.81  # m/s²
    timestep: float = 0.001  # seconds (1 kHz control loop)
    num_solver_iterations: int = 150
    use_real_time_simulation: bool = False
    
    # Damping parameters
    linear_damping: float = 0.04  # Rayleigh damping
    angular_damping: float = 0.04
    
    # Contact dynamics
    friction_coefficient: float = 0.8  # Ground contact
    rolling_friction: float = 0.001  # Rolling resistance
    restitution: float = 0.3  # Bounce coefficient


class EggSimulator:
    """
    High-precision physics simulator for egg-shaped bottom-heavy systems.
    
    Responsibilities:
    - Load/construct egg rigid body
    - Apply motor forces/torques
    - Integrate dynamics at high precision
    - Track tilt angle, angular velocity, energy state
    - Provide sensor readings (angle, gyro, accelerometer)
    """
    
    def __init__(self, egg_model, config: PhysicsConfig = None, gui: bool = False):
        """
        Initialize simulator.
        
        Args:
            egg_model: EggModel instance with geometry and mass properties
            config: PhysicsConfig; uses defaults if None
            gui: Enable PyBullet GUI for visualization
        """
        self.egg_model = egg_model
        self.config = config or PhysicsConfig()
        self.gui = gui
        
        # PyBullet connection
        self.client_id = None
        self.egg_body_id = None
        self.ground_plane_id = None
        
        # State tracking
        self.time = 0.0
        self.tilt_angle = 0.0
        self.tilt_rate = 0.0
        self.energy_consumed = 0.0
        self.power_samples = []
        
        self._initialize_physics()
    
    def _initialize_physics(self):
        """Set up PyBullet environment and load egg model."""
        # Connect to PyBullet
        if self.gui:
            self.client_id = p.connect(p.GUI)
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
        else:
            self.client_id = p.connect(p.DIRECT)
        
        # Set physics engine parameters
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -self.config.gravity, physicsClientId=self.client_id)
        p.setTimeStep(self.config.timestep, physicsClientId=self.client_id)
        p.setPhysicsEngineParameter(
            numSolverIterations=self.config.num_solver_iterations,
            physicsClientId=self.client_id
        )
        
        # Load ground plane
        self.ground_plane_id = p.loadURDF(
            "plane.urdf",
            basePosition=[0, 0, 0],
            physicsClientId=self.client_id
        )
        p.changeDynamics(
            self.ground_plane_id,
            -1,
            lateralFriction=self.config.friction_coefficient,
            restitution=self.config.restitution,
            physicsClientId=self.client_id
        )
        
        # Load egg body
        self.egg_body_id = self._load_egg_body()
    
    def _load_egg_body(self) -> int:
        """
        Load egg geometry into PyBullet as a multi-shape compound body.
        Respects mass distribution and center-of-mass offset.
        
        Returns:
            Body ID for the egg
        """
        # For now, use a simple sphere approximation
        # TODO: Load from CAD geometry
        mass = self.egg_model.mass / 1000.0  # convert grams to kg
        
        # Create compound body with offset COM
        base_position = [0, 0, 0.10]  # Start 10cm above ground
        base_orientation = p.getQuaternionFromEuler([0, 0, 0])
        
        body_id = p.createMultiBody(
            baseMass=mass,
            baseShape=p.GEOM_SPHERE,
            baseRadius=0.05,  # 50mm radius
            basePosition=base_position,
            baseOrientation=base_orientation,
            physicsClientId=self.client_id
        )
        
        # Set damping
        p.changeDynamics(
            body_id,
            -1,
            linearDamping=self.config.linear_damping,
            angularDamping=self.config.angular_damping,
            lateralFriction=self.config.friction_coefficient,
            rollingFriction=self.config.rolling_friction,
            physicsClientId=self.client_id
        )
        
        return body_id
    
    def step(self, motor_force: np.ndarray = None, motor_torque: np.ndarray = None):
        """
        Advance simulation by one timestep.
        
        Args:
            motor_force: 3D force vector applied to egg center (N)
            motor_torque: 3D torque vector applied to egg (N·m)
        """
        if motor_force is not None:
            p.applyExternalForce(
                self.egg_body_id,
                -1,
                list(motor_force),
                [0, 0, 0],
                p.WORLD_FRAME,
                physicsClientId=self.client_id
            )
        
        if motor_torque is not None:
            p.applyExternalTorque(
                self.egg_body_id,
                -1,
                list(motor_torque),
                p.WORLD_FRAME,
                physicsClientId=self.client_id
            )
        
        # Step physics
        p.stepSimulation(physicsClientId=self.client_id)
        self.time += self.config.timestep
        
        # Update state
        self._update_state()
    
    def _update_state(self):
        """Extract tilt angle, rate, and other state from PyBullet."""
        pos, orn = p.getBasePositionAndOrientation(
            self.egg_body_id,
            physicsClientId=self.client_id
        )
        lin_vel, ang_vel = p.getBaseVelocity(
            self.egg_body_id,
            physicsClientId=self.client_id
        )
        
        # Euler angles from quaternion (roll, pitch, yaw)
        roll, pitch, yaw = p.getEulerFromQuaternion(orn)
        
        # Tilt angle is pitch (rotation around Y axis)
        self.tilt_angle = pitch  # radians
        self.tilt_rate = ang_vel[1]  # radians/second
        
        # Store orientation for later use
        self.current_position = np.array(pos)
        self.current_orientation = np.array(orn)
        self.current_lin_vel = np.array(lin_vel)
        self.current_ang_vel = np.array(ang_vel)
    
    def get_tilt_angle(self) -> float:
        """Return current tilt angle in radians."""
        return self.tilt_angle
    
    def get_tilt_angle_degrees(self) -> float:
        """Return current tilt angle in degrees."""
        return np.degrees(self.tilt_angle)
    
    def get_tilt_rate(self) -> float:
        """Return current tilt angular velocity in rad/s."""
        return self.tilt_rate
    
    def get_time(self) -> float:
        """Return elapsed simulation time."""
        return self.time
    
    def record_power(self, power: float):
        """Record instantaneous power consumption."""
        self.power_samples.append(power)
        self.energy_consumed += power * self.config.timestep
    
    def get_average_power(self) -> float:
        """Return average power consumption so far (Watts)."""
        if not self.power_samples:
            return 0.0
        return np.mean(self.power_samples)
    
    def get_total_energy(self) -> float:
        """Return total energy consumed so far (Joules)."""
        return self.energy_consumed
    
    def reset(self):
        """Reset egg to initial position and zero velocity."""
        p.resetBasePositionAndOrientation(
            self.egg_body_id,
            [0, 0, 0.10],
            p.getQuaternionFromEuler([0, 0, 0]),
            physicsClientId=self.client_id
        )
        p.resetBaseVelocity(
            self.egg_body_id,
            [0, 0, 0],
            [0, 0, 0],
            physicsClientId=self.client_id
        )
        
        self.time = 0.0
        self.tilt_angle = 0.0
        self.tilt_rate = 0.0
        self.energy_consumed = 0.0
        self.power_samples = []
    
    def close(self):
        """Clean up PyBullet connection."""
        if self.client_id is not None:
            p.disconnect(physicsClientId=self.client_id)


class SimulationRecorder:
    """Records simulation state trajectories for analysis."""
    
    def __init__(self):
        self.times = []
        self.tilt_angles = []
        self.tilt_rates = []
        self.motor_forces = []
        self.motor_torques = []
        self.powers = []
    
    def record(self, time: float, tilt_angle: float, tilt_rate: float,
               motor_force: np.ndarray, motor_torque: np.ndarray, power: float):
        """Record one sample of simulation state."""
        self.times.append(time)
        self.tilt_angles.append(tilt_angle)
        self.tilt_rates.append(tilt_rate)
        self.motor_forces.append(motor_force.copy() if motor_force is not None else None)
        self.motor_torques.append(motor_torque.copy() if motor_torque is not None else None)
        self.powers.append(power)
    
    def to_arrays(self):
        """Convert to numpy arrays for analysis."""
        return {
            'times': np.array(self.times),
            'tilt_angles': np.array(self.tilt_angles),
            'tilt_rates': np.array(self.tilt_rates),
            'motor_forces': np.array(self.motor_forces) if self.motor_forces[0] is not None else None,
            'motor_torques': np.array(self.motor_torques) if self.motor_torques[0] is not None else None,
            'powers': np.array(self.powers),
        }
