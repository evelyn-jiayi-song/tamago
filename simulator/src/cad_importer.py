"""
CAD Geometry Importer

Handles loading CAD models from Fusion 360 exports and other formats.
Converts geometry to physics-engine-compatible representations.
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Union
from dataclasses import dataclass
import json


@dataclass
class CADMesh:
    """Represents a loaded CAD mesh."""
    vertices: np.ndarray  # N×3 array of vertex positions (mm)
    faces: np.ndarray  # M×3 array of triangle face indices
    name: str = "mesh"
    
    def get_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return bounding box (min, max)."""
        return np.min(self.vertices, axis=0), np.max(self.vertices, axis=0)
    
    def get_center(self) -> np.ndarray:
        """Return geometric center."""
        min_bound, max_bound = self.get_bounds()
        return (min_bound + max_bound) / 2.0
    
    def translate(self, offset: np.ndarray):
        """Translate mesh by offset."""
        self.vertices += offset
    
    def scale(self, factor: float):
        """Scale mesh by factor."""
        self.vertices *= factor


class CADImporter:
    """
    Imports CAD geometry from various formats.
    
    Supported formats:
    - STEP (.step, .stp) - via trimesh
    - STL (.stl) - via trimesh
    - OBJ (.obj) - via trimesh
    - URDF (.urdf) - for Fusion 360 mechanism exports
    - YAML (.yaml) - custom parametric definitions
    """
    
    @staticmethod
    def import_file(filepath: Union[str, Path], name: str = None) -> CADMesh:
        """
        Load geometry from file.
        
        Args:
            filepath: Path to CAD file
            name: Optional name for mesh
        
        Returns:
            CADMesh instance
        
        Raises:
            ValueError: If file format unsupported or file not found
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"CAD file not found: {filepath}")
        
        suffix = filepath.suffix.lower()
        mesh_name = name or filepath.stem
        
        if suffix in ['.step', '.stp']:
            return CADImporter._import_step(filepath, mesh_name)
        elif suffix == '.stl':
            return CADImporter._import_stl(filepath, mesh_name)
        elif suffix == '.obj':
            return CADImporter._import_obj(filepath, mesh_name)
        elif suffix == '.urdf':
            return CADImporter._import_urdf(filepath, mesh_name)
        elif suffix == '.yaml':
            return CADImporter._import_yaml(filepath, mesh_name)
        else:
            raise ValueError(f"Unsupported CAD format: {suffix}")
    
    @staticmethod
    def _import_step(filepath: Path, name: str) -> CADMesh:
        """
        Import STEP file (requires trimesh).
        
        STEP is the standard export format from Fusion 360.
        """
        try:
            import trimesh
        except ImportError:
            raise ImportError("trimesh required for STEP import: pip install trimesh")
        
        try:
            mesh = trimesh.load(str(filepath))
            
            # Handle multi-mesh cases
            if isinstance(mesh, trimesh.Trimesh):
                vertices = mesh.vertices
                faces = mesh.faces
            else:
                # Merge multiple meshes
                vertices_list = [m.vertices for m in mesh.geometry.values()]
                faces_list = []
                vertex_offset = 0
                for m in mesh.geometry.values():
                    faces_list.append(m.faces + vertex_offset)
                    vertex_offset += len(m.vertices)
                
                vertices = np.vstack(vertices_list)
                faces = np.vstack(faces_list)
            
            # Convert to mm if needed (trimesh typically uses meters)
            # Heuristic: if bounds > 1000, already in mm
            bounds_max = np.max(np.abs(vertices))
            if bounds_max < 1000:
                vertices *= 1000  # Convert from meters to mm
            
            return CADMesh(vertices, faces, name)
        
        except Exception as e:
            raise ValueError(f"Failed to load STEP file: {e}")
    
    @staticmethod
    def _import_stl(filepath: Path, name: str) -> CADMesh:
        """Import STL file."""
        try:
            import trimesh
        except ImportError:
            raise ImportError("trimesh required for STL import: pip install trimesh")
        
        mesh = trimesh.load(str(filepath))
        vertices = mesh.vertices * 1000  # Convert to mm
        faces = mesh.faces
        
        return CADMesh(vertices, faces, name)
    
    @staticmethod
    def _import_obj(filepath: Path, name: str) -> CADMesh:
        """Import OBJ file."""
        try:
            import trimesh
        except ImportError:
            raise ImportError("trimesh required for OBJ import: pip install trimesh")
        
        mesh = trimesh.load(str(filepath))
        vertices = mesh.vertices * 1000  # Convert to mm
        faces = mesh.faces
        
        return CADMesh(vertices, faces, name)
    
    @staticmethod
    def _import_urdf(filepath: Path, name: str) -> CADMesh:
        """
        Import URDF file (robot description format).
        
        Fusion 360 can export mechanism URDFs.
        Extract mesh from <mesh> tags.
        """
        try:
            from xml.etree import ElementTree as ET
            import trimesh
        except ImportError:
            raise ImportError("xml and trimesh required for URDF import")
        
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Find mesh references
        meshes = []
        for geometry in root.findall('.//geometry/mesh'):
            mesh_file = geometry.get('filename')
            if mesh_file:
                # Resolve relative path
                mesh_path = filepath.parent / mesh_file
                if mesh_path.exists():
                    try:
                        mesh = trimesh.load(str(mesh_path))
                        meshes.append(mesh)
                    except:
                        pass
        
        if not meshes:
            raise ValueError("No meshes found in URDF file")
        
        # Combine all meshes
        if len(meshes) == 1:
            mesh = meshes[0]
            vertices = mesh.vertices * 1000
            faces = mesh.faces
        else:
            vertices_list = [m.vertices for m in meshes]
            faces_list = []
            vertex_offset = 0
            for m in meshes:
                faces_list.append(m.faces + vertex_offset)
                vertex_offset += len(m.vertices)
            
            vertices = np.vstack(vertices_list) * 1000
            faces = np.vstack(faces_list)
        
        return CADMesh(vertices, faces, name)
    
    @staticmethod
    def _import_yaml(filepath: Path, name: str) -> CADMesh:
        """
        Import from YAML parametric definition.
        
        Example YAML:
        ```
        type: ellipsoid
        semi_axes: [35, 35, 40]  # mm
        resolution: 20  # triangles per axis
        ```
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install PyYAML")
        
        with open(filepath, 'r') as f:
            config = yaml.safe_load(f)
        
        geom_type = config.get('type', 'sphere')
        
        if geom_type == 'sphere':
            radius = config.get('radius', 35)
            resolution = config.get('resolution', 20)
            vertices, faces = CADImporter._generate_sphere(radius, resolution)
        
        elif geom_type == 'ellipsoid':
            axes = config.get('semi_axes', [35, 35, 40])
            resolution = config.get('resolution', 20)
            vertices, faces = CADImporter._generate_ellipsoid(axes, resolution)
        
        else:
            raise ValueError(f"Unsupported YAML geometry type: {geom_type}")
        
        return CADMesh(vertices, faces, name)
    
    @staticmethod
    def _generate_sphere(radius: float, resolution: int) -> Tuple[np.ndarray, np.ndarray]:
        """Generate icosphere mesh."""
        try:
            import trimesh
            sphere = trimesh.creation.icosphere(subdivisions=max(1, resolution // 4), radius=radius)
            return sphere.vertices, sphere.faces
        except:
            # Fallback: UV sphere
            u = np.linspace(0, 2 * np.pi, resolution)
            v = np.linspace(0, np.pi, resolution)
            x = radius * np.outer(np.cos(u), np.sin(v))
            y = radius * np.outer(np.sin(u), np.sin(v))
            z = radius * np.outer(np.ones(np.size(u)), np.cos(v))
            
            vertices = np.column_stack([x.ravel(), y.ravel(), z.ravel()])
            # Simple triangulation
            faces = []
            for i in range(resolution - 1):
                for j in range(resolution - 1):
                    v0 = i * resolution + j
                    v1 = i * resolution + (j + 1)
                    v2 = (i + 1) * resolution + j
                    v3 = (i + 1) * resolution + (j + 1)
                    faces.append([v0, v1, v2])
                    faces.append([v1, v3, v2])
            
            return vertices, np.array(faces)
    
    @staticmethod
    def _generate_ellipsoid(semi_axes: Tuple[float, float, float], 
                           resolution: int) -> Tuple[np.ndarray, np.ndarray]:
        """Generate ellipsoid mesh."""
        a, b, c = semi_axes
        
        try:
            import trimesh
            sphere = trimesh.creation.icosphere(subdivisions=max(1, resolution // 4), radius=1.0)
            vertices = sphere.vertices * np.array([a, b, c])
            return vertices, sphere.faces
        except:
            # Fallback: UV ellipsoid
            u = np.linspace(0, 2 * np.pi, resolution)
            v = np.linspace(0, np.pi, resolution)
            x = a * np.outer(np.cos(u), np.sin(v))
            y = b * np.outer(np.sin(u), np.sin(v))
            z = c * np.outer(np.ones(np.size(u)), np.cos(v))
            
            vertices = np.column_stack([x.ravel(), y.ravel(), z.ravel()])
            # Simple triangulation
            faces = []
            for i in range(resolution - 1):
                for j in range(resolution - 1):
                    v0 = i * resolution + j
                    v1 = i * resolution + (j + 1)
                    v2 = (i + 1) * resolution + j
                    v3 = (i + 1) * resolution + (j + 1)
                    faces.append([v0, v1, v2])
                    faces.append([v1, v3, v2])
            
            return vertices, np.array(faces)


class FusionExportHelper:
    """
    Helper for exporting from Fusion 360 and importing here.
    
    Fusion 360 export checklist:
    1. Select body in design
    2. Right-click → "Save as Mesh" or "Export"
    3. Choose format: STEP (.step) recommended
    4. Save to simulator/data/cad/ directory
    5. Use CADImporter.import_file() to load
    
    For parametric access:
    1. Export as URDF (for mechanisms)
    2. Or use "Export Design as YAML" if available
    """
    
    @staticmethod
    def list_cad_files(directory: str = "data/cad") -> list:
        """List available CAD files in directory."""
        directory = Path(directory)
        if not directory.exists():
            return []
        
        supported_extensions = ['.step', '.stp', '.stl', '.obj', '.urdf', '.yaml']
        files = [f for f in directory.glob('*') 
                if f.suffix.lower() in supported_extensions]
        return sorted(files)
    
    @staticmethod
    def create_example_config(output_path: str = "data/egg_models/example.yaml"):
        """Create example YAML configuration for egg model."""
        example = {
            'name': 'standard_egg_500g',
            'geometry': {
                'profile': 'ellipsoid',
                'semi_axes': [35, 35, 40],  # a, b, c in mm
                'contact_radius': 35,
                'surface_roughness': 0.1,
                'shell_thickness': 2
            },
            'mass': {
                'total': 500,  # grams
                'center_of_mass': [0, 0, -25],  # mm, relative to geometric center
                'inertia_tensor': [
                    [105000, 0, 0],
                    [0, 105000, 0],
                    [0, 0, 90000]
                ]  # g·mm²
            }
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        import yaml
        with open(output_path, 'w') as f:
            yaml.dump(example, f, default_flow_style=False)
        
        print(f"Example config created: {output_path}")
        return output_path
