#!/usr/bin/env python3
"""
Example: Run a baseline test of all 10 motor control methods.

Usage:
    python experiments/baseline_tests.py
    python experiments/baseline_tests.py --method 1 --duration 60 --target-angle 20
    python experiments/baseline_tests.py --output results/my_experiment.json
"""

import sys
import json
import argparse
import numpy as np
from pathlib import Path
from dataclasses import asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import (
    EggSimulator, PhysicsConfig, create_standard_egg,
    create_all_methods, MetricsCalculator, SimulationRecorder
)


def run_test(motor_method, egg_model, target_angle_deg=15.0, duration_sec=30.0, gui=False):
    """
    Run a single motor control method test.
    
    Args:
        motor_method: MotorMethod instance
        egg_model: EggModel instance
        target_angle_deg: Target tilt angle
        duration_sec: Simulation duration
        gui: Enable PyBullet GUI visualization
    
    Returns:
        (result, recorder) where result is EvaluationResult and recorder is SimulationRecorder
    """
    print(f"  Testing: {motor_method.name}")
    print(f"    Duration: {duration_sec}s, Target: {target_angle_deg}°")
    
    # Initialize simulator
    config = PhysicsConfig(timestep=0.001)  # 1 kHz loop
    sim = EggSimulator(egg_model, config=config, gui=gui)
    motor_method.reset()
    
    # Setup recorder
    recorder = SimulationRecorder()
    
    # Run simulation
    timestep = config.timestep
    num_steps = int(duration_sec / timestep)
    
    for step in range(num_steps):
        # Get current state
        tilt_angle_deg = sim.get_tilt_angle_degrees()
        tilt_rate = sim.get_tilt_rate()
        
        # Motor update
        force, torque = motor_method.update(np.radians(tilt_angle_deg), timestep)
        power = motor_method.get_power_consumption()
        
        # Step physics
        sim.step(motor_force=force, motor_torque=torque)
        sim.record_power(power)
        
        # Record
        recorder.record(
            time=sim.get_time(),
            tilt_angle=tilt_angle_deg,
            tilt_rate=tilt_rate,
            motor_force=force,
            motor_torque=torque,
            power=power
        )
        
        # Progress indicator every 5 seconds
        if (step + 1) % (int(5 / timestep)) == 0:
            print(f"      {step / num_steps * 100:.1f}% complete (t={sim.get_time():.1f}s)")
    
    # Compute metrics
    data = recorder.to_arrays()
    calculator = MetricsCalculator(target_angle_deg=target_angle_deg)
    
    result = calculator.evaluate(
        method_name=motor_method.name,
        times=data['times'],
        tilt_angles_deg=data['tilt_angles'],
        tilt_rates=data['tilt_rates'],
        motor_torques=data['motor_torques'],
        motor_forces=data['motor_forces'],
        power_samples=data['powers']
    )
    
    sim.close()
    
    return result, recorder


def run_baseline_study(duration_sec=30.0, target_angle_deg=15.0, output_file=None):
    """
    Run baseline tests for all 10 motor methods.
    
    Args:
        duration_sec: Duration per test
        target_angle_deg: Target angle for each test
        output_file: JSON file to save results
    """
    print("="*70)
    print("MOTOR CONTROL METHOD BASELINE STUDY")
    print("="*70)
    
    # Create egg model
    egg = create_standard_egg(mass_g=500, com_offset_mm=25)
    print(f"\nEgg Model:")
    print(egg.summary())
    
    # Create all methods
    methods = create_all_methods()
    print(f"\nTesting {len(methods)} motor control methods...")
    print()
    
    # Run tests
    results = []
    for i, method in enumerate(methods):
        print(f"[{i+1}/{len(methods)}] {method.name}")
        try:
            result, recorder = run_test(
                method, egg,
                target_angle_deg=target_angle_deg,
                duration_sec=duration_sec,
                gui=False
            )
            results.append(result)
            print(f"    ✓ Success: Score {result.overall_score:.1f}/100")
        except Exception as e:
            print(f"    ✗ Failed: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    print()
    
    # Print all results
    for result in results:
        print(result.summary())
    
    # Ranking table
    print("\n" + "="*70)
    print("METHOD RANKING (by overall score)")
    print("="*70)
    print(f"{'Rank':<6} {'Method':<30} {'Score':<8} {'Power':<10} {'Error':<10} {'Feasibility':<12}")
    print("-"*70)
    
    sorted_results = sorted(results, key=lambda r: r.overall_score, reverse=True)
    for rank, result in enumerate(sorted_results, 1):
        print(f"{rank:<6} {result.method_name:<30} {result.overall_score:<8.1f} "
              f"{result.energy.average_power:<10.2f}W {result.control_precision.rms_error:<10.2f}° "
              f"{result.feasibility_rating:<12}")
    
    # Save results to JSON if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        output_data = {
            'timestamp': np.datetime64('now').astype(str),
            'egg_model': egg.name,
            'test_duration_s': duration_sec,
            'target_angle_deg': target_angle_deg,
            'results': [
                {
                    'method_name': r.method_name,
                    'overall_score': float(r.overall_score),
                    'feasibility': r.feasibility_rating,
                    'control_precision': asdict(r.control_precision),
                    'energy': asdict(r.energy),
                    'robustness': asdict(r.robustness),
                    'mechanical': asdict(r.mechanical),
                }
                for r in results
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run baseline tests for all motor control methods'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=30.0,
        help='Duration per test in seconds (default: 30)'
    )
    parser.add_argument(
        '--target-angle',
        type=float,
        default=15.0,
        help='Target tilt angle in degrees (default: 15)'
    )
    parser.add_argument(
        '--method',
        type=int,
        help='Test specific method by index (1-10)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='results/baseline_study.json',
        help='Output JSON file for results'
    )
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Enable PyBullet GUI visualization'
    )
    
    args = parser.parse_args()
    
    if args.method:
        # Test single method
        methods = create_all_methods()
        if 1 <= args.method <= len(methods):
            egg = create_standard_egg()
            method = methods[args.method - 1]
            result, _ = run_test(method, egg, args.target_angle, args.duration, args.gui)
            print(result.summary())
        else:
            print(f"Invalid method index: {args.method}. Must be 1-{len(methods)}")
    else:
        # Run baseline study
        run_baseline_study(
            duration_sec=args.duration,
            target_angle_deg=args.target_angle,
            output_file=args.output
        )
