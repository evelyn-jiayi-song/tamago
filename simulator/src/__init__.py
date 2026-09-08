"""
Simulator package initialization.
"""

__version__ = "0.1.0"

from .physics_engine import EggSimulator, PhysicsConfig, SimulationRecorder
from .egg_model import EggModel, create_standard_egg
from .motor_methods import (
    EccentricMassSpinner,
    LinearSolenoidSlider,
    EAPMuscleActuator,
    HydraulicPistonActuator,
    VoiceCoilActuator,
    ReactivePendulum,
    PiezoStackArray,
    SMASpringActuator,
    BLDCCamFollower,
    AdaptiveResonanceTracker,
    create_all_methods
)
from .metrics import MetricsCalculator, EvaluationResult
from .cad_importer import CADImporter, CADMesh

__all__ = [
    'EggSimulator',
    'PhysicsConfig',
    'SimulationRecorder',
    'EggModel',
    'create_standard_egg',
    'EccentricMassSpinner',
    'LinearSolenoidSlider',
    'EAPMuscleActuator',
    'HydraulicPistonActuator',
    'VoiceCoilActuator',
    'ReactivePendulum',
    'PiezoStackArray',
    'SMASpringActuator',
    'BLDCCamFollower',
    'AdaptiveResonanceTracker',
    'create_all_methods',
    'MetricsCalculator',
    'EvaluationResult',
    'CADImporter',
    'CADMesh',
]
