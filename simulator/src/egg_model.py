"""
Egg body model with configurable mass distribution and center-of-mass.
Bridges CAD geometry with physics simulation parameters.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class MassDistribution:
    """Describes mass distribution in the egg."""
    total_mass: float  # grams
    center_of_mass: Tuple[float, float, float]  # mm, relative to geometric center
    inertia_tensor: np.ndarray  # 3x3 matrix, g·mm²
    
    def to_SI(self) -> Tuple[float, np.ndarray, np.ndarray]:
        """Convert to SI units (kg, m, kg·m²)."""
        mass_kg = self.total_mass / 1000.0
        com_m = np.array(self.center_of_mass) / 1000.0
        inertia_kg_m2 = self.inertia_tensor / 1e6  # 1 g·mm² = 1e-6 kg·m²
        return mass_kg, com_m, inertia_kg_m2


@dataclass
class EggGeometry:
    """Describes egg shape and contact properties."""
    profile: str  # 'sphere', 'ellipsoid', 'CAD', etc.
    semi_axes: Optional[Tuple[float, float, float]]  # mm (a, b, c for ellipsoid)
    contact_radius: float  # mm, effective contact radius for rolling
    surface_roughness: float  # mm, for contact friction
    shell_thickness: float  # mm, for stress analysis


class EggModel:
    """
    Complete egg model combining geometry, mass, and physical properties.
    
    Designed to be loaded from CAD exports and configured with measured
    or calculated mass/CoM parameters.
    """
    
    def __init__(self, 
                 geometry: EggGeometry,
                 mass_distribution: MassDistribution,
                 name: str = "egg"):
        """
        Initialize egg model.
        
        Args:
            geometry: EggGeometry instance
            mass_distribution: MassDistribution instance
            name: Identifier for this egg configuration
        """
        self.geometry = geometry
        self.mass_distribution = mass_distribution
        self.name = name
        
        # Validate physical consistency
        self._validate()
    
    @classmethod
    def from_dict(cls, config: dict) -> 'EggModel':
        """
        Load egg model from configuration dictionary.
        
        Expected format:
        {
            'name': 'egg_v1',
            'geometry': {
                'profile': 'ellipsoid',
                'semi_axes': [30, 35, 40],  # mm
                'contact_radius': 35,
                'surface_roughness': 0.1,
                'shell_thickness': 2
            },
            'mass': {
                'total': 500,  # grams
                'center_of_mass': [0, 0, -25],  # mm
                'inertia_tensor': [[1e5, 0, 0], [0, 1e5, 0], [0, 0, 9e4]]
            }
        }
        """
        geom = EggGeometry(
            profile=config['geometry']['profile'],
            semi_axes=tuple(config['geometry'].get('semi_axes', [35, 35, 40])),
            contact_radius=config['geometry']['contact_radius'],
            surface_roughness=config['geometry']['surface_roughness'],
            shell_thickness=config['geometry']['shell_thickness']
        )
        
        mass = MassDistribution(
            total_mass=config['mass']['total'],
            center_of_mass=tuple(config['mass']['center_of_mass']),
            inertia_tensor=np.array(config['mass']['inertia_tensor'])
        )
        
        return cls(geom, mass, config.get('name', 'egg'))
    
    def _validate(self):
        """Check physical consistency of model."""
        # Center of mass should be below geometric center (bottom-heavy)
        com_z = self.mass_distribution.center_of_mass[2]
        if com_z > 0:
            raise ValueError(f"CoM z={com_z} mm is above geometric center; egg must be bottom-heavy")
        
        # Inertia tensor should be positive definite
        eigenvalues = np.linalg.eigvals(self.mass_distribution.inertia_tensor)
        if np.any(eigenvalues <= 0):
            raise ValueError(f"Inertia tensor not positive definite: eigenvalues={eigenvalues}")
        
        # Radius of gyration check (sanity check)
        mass = self.mass_distribution.total_mass
        radius_gyration = np.sqrt(np.trace(self.mass_distribution.inertia_tensor) / (3 * mass))
        expected_radius = max(self.geometry.semi_axes or [40]) * 0.8
        if radius_gyration > expected_radius * 1.5:
            print(f"Warning: Radius of gyration {radius_gyration:.1f} mm seems large for egg size")
    
    @property
    def mass(self) -> float:
        """Return total mass in grams."""
        return self.mass_distribution.total_mass
    
    @property
    def center_of_mass(self) -> np.ndarray:
        """Return center of mass in mm (relative to geometric center)."""
        return np.array(self.mass_distribution.center_of_mass)
    
    @property
    def inertia(self) -> np.ndarray:
        """Return inertia tensor in g·mm²."""
        return self.mass_distribution.inertia_tensor
    
    def get_restoring_torque_at_angle(self, tilt_angle: float) -> float:
        """
        Calculate gravitational restoring torque at given tilt angle.
        
        Torque from gravity: τ = m·g·d·sin(θ)
        where d is CoM distance from contact point
        
        Args:
            tilt_angle: Angle in radians
        
        Returns:
            Torque in N·mm (positive = restoring)
        """
        mass_kg = self.mass / 1000.0
        g = 9.81  # m/s²
        
        # Distance from contact point to CoM
        com_offset = np.linalg.norm(self.center_of_mass)  # mm
        com_offset_m = com_offset / 1000.0
        
        torque_nm = mass_kg * g * com_offset_m * np.sin(tilt_angle)
        torque_nmm = torque_nm * 1e6  # Convert to N·mm
        
        return torque_nmm
    
    def get_natural_frequency(self) -> float:
        """
        Estimate natural rocking frequency (for small oscillations).
        
        For bottom-heavy system: f ≈ (1/2π)·√(restoring_torque_gradient / inertia)
        
        Returns:
            Frequency in Hz
        """
        # Linearize: τ ≈ -k·θ where k = m·g·d
        mass_kg = self.mass / 1000.0
        g = 9.81
        d_m = np.linalg.norm(self.center_of_mass) / 1000.0
        
        stiffness = mass_kg * g * d_m  # N·m / rad
        
        # Use principal axis of inertia tensor (around Y-axis, typically)
        inertia_yy = self.inertia[1, 1] / 1e6  # kg·m²
        
        omega_n = np.sqrt(stiffness / inertia_yy)  # rad/s
        f_n = omega_n / (2 * np.pi)
        
        return f_n
    
    def get_damping_ratio_estimate(self, damping_coefficient: float = 0.04) -> float:
        """
        Estimate damping ratio (for control design).
        
        ζ = c / (2·√(k·m))
        
        Args:
            damping_coefficient: Rayleigh damping coefficient (0-1)
        
        Returns:
            Damping ratio (0 = undamped, 1 = critically damped)
        """
        mass_kg = self.mass / 1000.0
        g = 9.81
        d_m = np.linalg.norm(self.center_of_mass) / 1000.0
        
        stiffness = mass_kg * g * d_m
        inertia_yy = self.inertia[1, 1] / 1e6
        
        omega_n = np.sqrt(stiffness / inertia_yy)
        effective_damping = damping_coefficient * inertia_yy  # c = 2·damping_coeff·inertia
        
        zeta = effective_damping / (2 * np.sqrt(stiffness * mass_kg))
        
        return zeta
    
    def summary(self) -> str:
        """Return human-readable summary of egg model."""
        lines = [
            f"Egg Model: {self.name}",
            f"  Mass: {self.mass:.1f} g",
            f"  Center of Mass offset: {self.center_of_mass} mm",
            f"  Geometry: {self.geometry.profile}",
            f"  Natural frequency (est.): {self.get_natural_frequency():.2f} Hz",
            f"  Damping ratio (est.): {self.get_damping_ratio_estimate():.2f}",
            f"  Restoring torque at 10°: {self.get_restoring_torque_at_angle(np.radians(10)):.0f} N·mm",
        ]
        return "\n".join(lines)


# Factory functions for common test cases

def create_standard_egg(mass_g: float = 500, com_offset_mm: float = 25) -> EggModel:
    """
    Create a standard test egg with common parameters.
    
    Args:
        mass_g: Total mass in grams
        com_offset_mm: Center-of-mass distance below geometric center
    
    Returns:
        EggModel instance
    """
    # Assume egg is roughly ellipsoidal, 35x35x40 mm
    geometry = EggGeometry(
        profile='ellipsoid',
        semi_axes=(35, 35, 40),
        contact_radius=35,
        surface_roughness=0.1,
        shell_thickness=2
    )
    
    # Inertia tensor (approximate for ellipsoid with COM offset)
    # Principal moments: Ixx, Iyy, Izz
    a, b, c = 35, 35, 40
    I_xx = (mass_g / 5) * (b**2 + c**2)  # g·mm²
    I_yy = (mass_g / 5) * (a**2 + c**2)
    I_zz = (mass_g / 5) * (a**2 + b**2)
    
    inertia = np.diag([I_xx, I_yy, I_zz])
    
    mass_dist = MassDistribution(
        total_mass=mass_g,
        center_of_mass=(0, 0, -com_offset_mm),
        inertia_tensor=inertia
    )
    
    return EggModel(geometry, mass_dist, f"standard_egg_{mass_g}g")
