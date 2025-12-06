"""
Terrain Analysis Service for slope, aspect, and elevation analysis.
Uses Rasterio for raster data processing and NumPy for calculations.
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Optional

import numpy as np
import rasterio
from shapely.geometry import box, mapping

logger = logging.getLogger("sitelayout.terrain_analysis")

# Default cache duration (7 days)
DEFAULT_CACHE_DURATION = timedelta(days=7)

# Slope classification thresholds (in degrees)
SLOPE_CLASSES = {
    "flat": (0, 2),  # 0-2 degrees
    "gentle": (2, 5),  # 2-5 degrees
    "moderate": (5, 10),  # 5-10 degrees
    "steep": (10, 20),  # 10-20 degrees
    "very_steep": (20, 90),  # >20 degrees
}

# Aspect direction names (compass directions)
ASPECT_DIRECTIONS = {
    "N": (337.5, 22.5),
    "NE": (22.5, 67.5),
    "E": (67.5, 112.5),
    "SE": (112.5, 157.5),
    "S": (157.5, 202.5),
    "SW": (202.5, 247.5),
    "W": (247.5, 292.5),
    "NW": (292.5, 337.5),
}


@dataclass
class ProgressTracker:
    """Tracks progress of terrain analysis."""

    total_steps: int = 6
    current_step: int = 0
    step_name: str = "initializing"
    progress_percent: int = 0
    callback: Optional[Callable[[int, str], None]] = None

    def update(self, step: int, name: str) -> None:
        """Update progress."""
        self.current_step = step
        self.step_name = name
        self.progress_percent = int((step / self.total_steps) * 100)
        logger.info(f"Progress: {self.progress_percent}% - {name}")
        if self.callback:
            self.callback(self.progress_percent, name)


@dataclass
class ElevationStats:
    """Elevation statistics."""

    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    nodata_count: int = 0
    valid_count: int = 0


@dataclass
class SlopeStats:
    """Slope analysis statistics."""

    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    classification: dict[str, float] = field(default_factory=dict)
    raster_path: Optional[str] = None
    raster_size: int = 0


@dataclass
class AspectStats:
    """Aspect analysis statistics."""

    distribution: dict[str, float] = field(default_factory=dict)
    raster_path: Optional[str] = None
    raster_size: int = 0


@dataclass
class TerrainAnalysisResult:
    """Complete terrain analysis result."""

    success: bool
    elevation_stats: Optional[ElevationStats] = None
    slope_stats: Optional[SlopeStats] = None
    aspect_stats: Optional[AspectStats] = None
    hillshade_path: Optional[str] = None
    hillshade_size: int = 0
    dem_source: str = "unknown"
    dem_resolution: float = 0.0
    dem_crs: str = "unknown"
    bounds_wkt: str = ""
    bounds_geojson: dict = field(default_factory=dict)
    processing_time: float = 0.0
    memory_peak_mb: float = 0.0
    input_hash: str = ""
    error_message: Optional[str] = None


def calculate_input_hash(
    dem_path: str,
    bounds: Optional[tuple[float, float, float, float]] = None,
    resolution: Optional[float] = None,
) -> str:
    """Calculate hash of input parameters for caching."""
    hash_input = f"{dem_path}"
    if bounds:
        hash_input += (
            f":{bounds[0]:.6f},{bounds[1]:.6f},{bounds[2]:.6f},{bounds[3]:.6f}"
        )
    if resolution:
        hash_input += f":{resolution:.2f}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


def load_dem(
    dem_path: str,
    bounds: Optional[tuple[float, float, float, float]] = None,
    target_crs: str = "EPSG:4326",
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Load DEM data from a raster file.

    Args:
        dem_path: Path to the DEM file (GeoTIFF, etc.)
        bounds: Optional bounding box (minx, miny, maxx, maxy) to clip
        target_crs: Target CRS for reprojection

    Returns:
        Tuple of (elevation_array, metadata_dict)
    """
    with rasterio.open(dem_path) as src:
        # Get source metadata
        src_crs = src.crs
        src_transform = src.transform
        src_bounds = src.bounds
        nodata = src.nodata if src.nodata is not None else -9999

        # Calculate resolution in meters (approximate for geographic CRS)
        if src_crs.is_geographic:
            # Approximate meters per degree at center latitude
            center_lat = (src_bounds.bottom + src_bounds.top) / 2
            meters_per_degree = 111320 * np.cos(np.radians(center_lat))
            resolution = abs(src_transform[0]) * meters_per_degree
        else:
            resolution = abs(src_transform[0])

        # Read data
        if bounds:
            # Create window from bounds
            from rasterio.windows import from_bounds as window_from_bounds

            window = window_from_bounds(*bounds, src_transform)
            data = src.read(1, window=window)
            # Update transform for the window
            window_transform = rasterio.windows.transform(window, src_transform)
            actual_bounds = bounds
        else:
            data = src.read(1)
            window_transform = src_transform
            actual_bounds = (
                src_bounds.left,
                src_bounds.bottom,
                src_bounds.right,
                src_bounds.top,
            )

        # Handle nodata values
        data = data.astype(np.float64)
        if nodata is not None:
            data[data == nodata] = np.nan

        metadata = {
            "crs": str(src_crs),
            "transform": window_transform,
            "bounds": actual_bounds,
            "resolution": resolution,
            "shape": data.shape,
            "nodata": nodata,
            "source": dem_path,
        }

        return data, metadata


def calculate_slope(
    elevation: np.ndarray,
    cell_size: float,
    output_path: Optional[str] = None,
    transform: Optional[Any] = None,
    crs: Optional[str] = None,
) -> tuple[np.ndarray, SlopeStats]:
    """
    Calculate slope from elevation data.

    Uses gradient-based method: slope = arctan(sqrt(dz/dx² + dz/dy²))

    Args:
        elevation: 2D array of elevation values
        cell_size: Cell size in meters
        output_path: Optional path to save slope raster
        transform: Rasterio transform for output
        crs: CRS for output

    Returns:
        Tuple of (slope_array in degrees, SlopeStats)
    """
    # Handle NaN values for gradient calculation
    elevation_filled = np.where(np.isnan(elevation), 0, elevation)
    mask = np.isnan(elevation)

    # Calculate gradients using numpy
    # Use Sobel-like kernel for better results
    dy, dx = np.gradient(elevation_filled, cell_size)

    # Calculate slope in degrees
    slope_radians = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_degrees = np.degrees(slope_radians)

    # Restore NaN mask
    slope_degrees[mask] = np.nan

    # Calculate statistics (excluding NaN)
    valid_slope = slope_degrees[~np.isnan(slope_degrees)]
    if len(valid_slope) > 0:
        min_val = float(np.min(valid_slope))
        max_val = float(np.max(valid_slope))
        mean_val = float(np.mean(valid_slope))
        std_val = float(np.std(valid_slope))
    else:
        min_val = max_val = mean_val = std_val = 0.0

    # Calculate slope classification percentages
    classification = {}
    total_valid = len(valid_slope)
    if total_valid > 0:
        for class_name, (low, high) in SLOPE_CLASSES.items():
            count = np.sum((valid_slope >= low) & (valid_slope < high))
            classification[class_name] = round(float(count / total_valid) * 100, 2)

    raster_size = 0
    if output_path and transform and crs:
        # Save slope raster
        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=slope_degrees.shape[0],
            width=slope_degrees.shape[1],
            count=1,
            dtype=slope_degrees.dtype,
            crs=crs,
            transform=transform,
            nodata=np.nan,
            compress="lzw",
        ) as dst:
            dst.write(slope_degrees, 1)
        raster_size = os.path.getsize(output_path)

    stats = SlopeStats(
        min_value=min_val,
        max_value=max_val,
        mean_value=mean_val,
        std_value=std_val,
        classification=classification,
        raster_path=output_path,
        raster_size=raster_size,
    )

    return slope_degrees, stats


def calculate_aspect(
    elevation: np.ndarray,
    cell_size: float,
    output_path: Optional[str] = None,
    transform: Optional[Any] = None,
    crs: Optional[str] = None,
) -> tuple[np.ndarray, AspectStats]:
    """
    Calculate aspect (direction of slope) from elevation data.

    Aspect is measured clockwise from north (0-360 degrees).

    Args:
        elevation: 2D array of elevation values
        cell_size: Cell size in meters
        output_path: Optional path to save aspect raster
        transform: Rasterio transform for output
        crs: CRS for output

    Returns:
        Tuple of (aspect_array in degrees, AspectStats)
    """
    # Handle NaN values
    elevation_filled = np.where(np.isnan(elevation), 0, elevation)
    mask = np.isnan(elevation)

    # Calculate gradients
    dy, dx = np.gradient(elevation_filled, cell_size)

    # Calculate aspect in radians (from east, counter-clockwise)
    aspect_radians = np.arctan2(-dy, dx)

    # Convert to degrees (from north, clockwise)
    aspect_degrees = np.degrees(aspect_radians)
    # Convert from math convention to compass convention
    aspect_degrees = (90.0 - aspect_degrees) % 360.0

    # Restore NaN mask
    aspect_degrees[mask] = np.nan

    # Set flat areas (where slope is ~0) to -1 (no aspect)
    slope_magnitude = np.sqrt(dx**2 + dy**2)
    flat_threshold = 0.001  # Very small slope threshold
    aspect_degrees[slope_magnitude < flat_threshold] = -1

    # Calculate aspect distribution
    valid_aspect = aspect_degrees[(~np.isnan(aspect_degrees)) & (aspect_degrees >= 0)]
    distribution = {}
    total_valid = len(valid_aspect)

    if total_valid > 0:
        for direction, (low, high) in ASPECT_DIRECTIONS.items():
            if direction == "N":
                # North wraps around 360
                count = np.sum((valid_aspect >= low) | (valid_aspect < high))
            else:
                count = np.sum((valid_aspect >= low) & (valid_aspect < high))
            distribution[direction] = round(float(count / total_valid) * 100, 2)

    raster_size = 0
    if output_path and transform and crs:
        # Save aspect raster
        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=aspect_degrees.shape[0],
            width=aspect_degrees.shape[1],
            count=1,
            dtype=aspect_degrees.dtype,
            crs=crs,
            transform=transform,
            nodata=np.nan,
            compress="lzw",
        ) as dst:
            dst.write(aspect_degrees, 1)
        raster_size = os.path.getsize(output_path)

    stats = AspectStats(
        distribution=distribution,
        raster_path=output_path,
        raster_size=raster_size,
    )

    return aspect_degrees, stats


def calculate_hillshade(
    elevation: np.ndarray,
    cell_size: float,
    azimuth: float = 315.0,
    altitude: float = 45.0,
    output_path: Optional[str] = None,
    transform: Optional[Any] = None,
    crs: Optional[str] = None,
) -> tuple[np.ndarray, int]:
    """
    Calculate hillshade for visualization.

    Args:
        elevation: 2D array of elevation values
        cell_size: Cell size in meters
        azimuth: Sun azimuth angle (default 315 = NW)
        altitude: Sun altitude angle (default 45 degrees)
        output_path: Optional path to save hillshade raster
        transform: Rasterio transform for output
        crs: CRS for output

    Returns:
        Tuple of (hillshade_array 0-255, file_size)
    """
    # Handle NaN values
    elevation_filled = np.where(np.isnan(elevation), 0, elevation)
    mask = np.isnan(elevation)

    # Calculate gradients
    dy, dx = np.gradient(elevation_filled, cell_size)

    # Convert angles to radians
    azimuth_rad = np.radians(360.0 - azimuth + 90.0)
    altitude_rad = np.radians(altitude)

    # Calculate slope and aspect
    slope = np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dy, dx)

    # Calculate hillshade
    hillshade = np.cos(altitude_rad) * np.cos(slope) + np.sin(altitude_rad) * np.sin(
        slope
    ) * np.cos(azimuth_rad - aspect)

    # Scale to 0-255
    hillshade = ((hillshade + 1) / 2 * 255).astype(np.uint8)

    # Restore NaN mask (set to 0)
    hillshade[mask] = 0

    file_size = 0
    if output_path and transform and crs:
        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=hillshade.shape[0],
            width=hillshade.shape[1],
            count=1,
            dtype=np.uint8,
            crs=crs,
            transform=transform,
            compress="lzw",
        ) as dst:
            dst.write(hillshade, 1)
        file_size = os.path.getsize(output_path)

    return hillshade, file_size


def calculate_elevation_stats(elevation: np.ndarray) -> ElevationStats:
    """Calculate elevation statistics."""
    nodata_mask = np.isnan(elevation)
    valid_data = elevation[~nodata_mask]

    if len(valid_data) == 0:
        return ElevationStats(
            min_value=0.0,
            max_value=0.0,
            mean_value=0.0,
            std_value=0.0,
            nodata_count=int(np.sum(nodata_mask)),
            valid_count=0,
        )

    return ElevationStats(
        min_value=float(np.min(valid_data)),
        max_value=float(np.max(valid_data)),
        mean_value=float(np.mean(valid_data)),
        std_value=float(np.std(valid_data)),
        nodata_count=int(np.sum(nodata_mask)),
        valid_count=len(valid_data),
    )


def analyze_terrain(
    dem_path: str,
    output_dir: str,
    analysis_id: str,
    bounds: Optional[tuple[float, float, float, float]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> TerrainAnalysisResult:
    """
    Perform complete terrain analysis on a DEM file.

    Args:
        dem_path: Path to the DEM raster file
        output_dir: Directory to save output rasters
        analysis_id: Unique ID for this analysis (used in output filenames)
        bounds: Optional bounding box to clip analysis area
        progress_callback: Optional callback for progress updates

    Returns:
        TerrainAnalysisResult with all analysis data
    """
    start_time = time.time()
    progress = ProgressTracker(callback=progress_callback)

    try:
        # Step 1: Load DEM
        progress.update(1, "Loading DEM data")
        elevation, metadata = load_dem(dem_path, bounds)

        cell_size = metadata["resolution"]
        transform = metadata["transform"]
        crs = metadata["crs"]
        actual_bounds = metadata["bounds"]

        # Create bounds geometry
        bounds_geom = box(*actual_bounds)
        bounds_wkt = bounds_geom.wkt
        bounds_geojson = mapping(bounds_geom)

        # Calculate input hash for caching
        input_hash = calculate_input_hash(dem_path, actual_bounds, cell_size)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Step 2: Calculate elevation statistics
        progress.update(2, "Calculating elevation statistics")
        elevation_stats = calculate_elevation_stats(elevation)

        # Step 3: Calculate slope
        progress.update(3, "Calculating slope")
        slope_path = os.path.join(output_dir, f"{analysis_id}_slope.tif")
        _, slope_stats = calculate_slope(
            elevation, cell_size, slope_path, transform, crs
        )

        # Step 4: Calculate aspect
        progress.update(4, "Calculating aspect")
        aspect_path = os.path.join(output_dir, f"{analysis_id}_aspect.tif")
        _, aspect_stats = calculate_aspect(
            elevation, cell_size, aspect_path, transform, crs
        )

        # Step 5: Calculate hillshade
        progress.update(5, "Generating hillshade")
        hillshade_path = os.path.join(output_dir, f"{analysis_id}_hillshade.tif")
        _, hillshade_size = calculate_hillshade(
            elevation,
            cell_size,
            output_path=hillshade_path,
            transform=transform,
            crs=crs,
        )

        # Step 6: Finalize
        progress.update(6, "Finalizing analysis")
        processing_time = time.time() - start_time

        # Estimate peak memory (rough estimate based on array sizes)
        array_memory = elevation.nbytes * 4  # Elevation + slope + aspect + hillshade
        memory_peak_mb = array_memory / (1024 * 1024)

        return TerrainAnalysisResult(
            success=True,
            elevation_stats=elevation_stats,
            slope_stats=slope_stats,
            aspect_stats=aspect_stats,
            hillshade_path=hillshade_path,
            hillshade_size=hillshade_size,
            dem_source=dem_path,
            dem_resolution=cell_size,
            dem_crs=crs,
            bounds_wkt=bounds_wkt,
            bounds_geojson=bounds_geojson,
            processing_time=processing_time,
            memory_peak_mb=memory_peak_mb,
            input_hash=input_hash,
        )

    except Exception as e:
        logger.exception("Error during terrain analysis")
        return TerrainAnalysisResult(
            success=False,
            error_message=f"Terrain analysis failed: {str(e)}",
            processing_time=time.time() - start_time,
        )


def get_elevation_at_points(
    dem_path: str,
    points: list[tuple[float, float]],
) -> list[Optional[float]]:
    """
    Extract elevation values at specific points.

    Args:
        dem_path: Path to the DEM file
        points: List of (longitude, latitude) tuples

    Returns:
        List of elevation values (None for points outside DEM or nodata)
    """
    elevations: list[Optional[float]] = []

    with rasterio.open(dem_path) as src:
        nodata = src.nodata

        for lon, lat in points:
            try:
                # Sample the raster at the point
                values = list(src.sample([(lon, lat)]))
                if values:
                    value = values[0][0]
                    if nodata is not None and value == nodata:
                        elevations.append(None)
                    elif np.isnan(value):
                        elevations.append(None)
                    else:
                        elevations.append(float(value))
                else:
                    elevations.append(None)
            except Exception:
                elevations.append(None)

    return elevations


def get_terrain_profile(
    dem_path: str,
    start_point: tuple[float, float],
    end_point: tuple[float, float],
    num_samples: int = 100,
) -> dict[str, Any]:
    """
    Extract terrain profile along a line.

    Args:
        dem_path: Path to the DEM file
        start_point: (lon, lat) start point
        end_point: (lon, lat) end point
        num_samples: Number of sample points along the line

    Returns:
        Dictionary with profile data
    """
    # Generate sample points along the line
    lons = np.linspace(start_point[0], end_point[0], num_samples)
    lats = np.linspace(start_point[1], end_point[1], num_samples)
    points = list(zip(lons, lats))

    # Get elevations
    elevations = get_elevation_at_points(dem_path, points)

    # Calculate distances
    from math import atan2, cos, radians, sin, sqrt

    def haversine(lon1, lat1, lon2, lat2):
        """Calculate distance between two points in meters."""
        R = 6371000  # Earth radius in meters
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    distances = [0.0]
    for i in range(1, len(points)):
        dist = haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
        distances.append(distances[-1] + dist)

    # Calculate elevation gain and loss
    elevation_gain = 0.0
    elevation_loss = 0.0
    for i in range(1, len(elevations)):
        curr = elevations[i]
        prev = elevations[i - 1]
        if curr is not None and prev is not None:
            diff = curr - prev
            if diff > 0:
                elevation_gain += diff
            else:
                elevation_loss += abs(diff)

    return {
        "points": [{"lon": p[0], "lat": p[1]} for p in points],
        "elevations": elevations,
        "distances": distances,
        "total_distance": distances[-1] if distances else 0,
        "elevation_gain": elevation_gain,
        "elevation_loss": elevation_loss,
    }
