"""
Cut/Fill Volume Estimation Service.

This service calculates earthwork volumes for asset foundations and road construction
using grid-based methods with NumPy for efficient computation.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import rasterio
from shapely.geometry import LineString, Point, Polygon

logger = logging.getLogger("sitelayout.volume_estimation")

# Earth radius for distance calculations
EARTH_RADIUS_M = 6371000
METERS_PER_DEGREE_LAT = 111320


@dataclass
class ProgressTracker:
    """Tracks progress of volume estimation."""

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
class AssetVolumeResult:
    """Volume estimation result for a single asset."""

    asset_id: int
    position: tuple[float, float]  # (lon, lat)
    foundation_type: str
    cut_volume_m3: float = 0.0
    fill_volume_m3: float = 0.0
    net_volume_m3: float = 0.0  # Positive = net cut, negative = net fill
    footprint_area_m2: float = 0.0
    avg_existing_elevation: float = 0.0
    design_elevation: float = 0.0
    max_cut_depth: float = 0.0
    max_fill_depth: float = 0.0
    grid_cells_analyzed: int = 0


@dataclass
class RoadSegmentVolumeResult:
    """Volume estimation result for a road segment."""

    segment_id: int
    from_asset: int
    to_asset: int
    cut_volume_m3: float = 0.0
    fill_volume_m3: float = 0.0
    net_volume_m3: float = 0.0
    road_length_m: float = 0.0
    road_area_m2: float = 0.0
    avg_cut_depth: float = 0.0
    avg_fill_depth: float = 0.0
    max_cut_depth: float = 0.0
    max_fill_depth: float = 0.0
    grid_cells_analyzed: int = 0


@dataclass
class VolumeEstimationResult:
    """Complete volume estimation result."""

    success: bool

    # Asset volumes
    asset_volumes: list[AssetVolumeResult] = field(default_factory=list)
    total_asset_cut_volume_m3: float = 0.0
    total_asset_fill_volume_m3: float = 0.0
    total_asset_net_volume_m3: float = 0.0

    # Road volumes
    road_volumes: list[RoadSegmentVolumeResult] = field(default_factory=list)
    total_road_cut_volume_m3: float = 0.0
    total_road_fill_volume_m3: float = 0.0
    total_road_net_volume_m3: float = 0.0

    # Project totals
    total_cut_volume_m3: float = 0.0
    total_fill_volume_m3: float = 0.0
    total_net_volume_m3: float = 0.0
    cut_fill_ratio: float = 0.0  # Ideal is 1.0 (balanced)

    # Grid data for 3D visualization
    visualization_data: Optional[dict[str, Any]] = None

    # Metadata
    dem_resolution: float = 0.0
    grid_cell_size: float = 0.0
    total_cells_analyzed: int = 0
    processing_time: float = 0.0
    memory_peak_mb: float = 0.0

    error_message: Optional[str] = None


def meters_to_degrees(meters: float, latitude: float) -> float:
    """Convert meters to degrees at a given latitude."""
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * np.cos(np.radians(latitude))
    avg_meters_per_degree = (METERS_PER_DEGREE_LAT + meters_per_degree_lon) / 2
    return meters / avg_meters_per_degree


def degrees_to_meters(degrees: float, latitude: float) -> float:
    """Convert degrees to meters at a given latitude."""
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * np.cos(np.radians(latitude))
    return degrees * (METERS_PER_DEGREE_LAT + meters_per_degree_lon) / 2


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great-circle distance between two points in meters."""
    lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(a))

    return EARTH_RADIUS_M * c


def get_foundation_dimensions(foundation_type: str) -> dict[str, Any]:
    """
    Get foundation dimensions based on type.

    Returns:
        Dictionary with width, length, and depth in meters
    """
    # Standard BESS foundation types
    foundation_specs = {
        "pad": {
            "width": 20.0,  # meters
            "length": 40.0,  # meters
            "depth": 0.5,  # pad foundation depth
            "description": "Concrete pad foundation for BESS containers",
        },
        "pier": {
            "width": 15.0,
            "length": 30.0,
            "depth": 1.5,  # pier foundation depth
            "description": "Pier foundation with point footings",
        },
        "strip": {
            "width": 18.0,
            "length": 35.0,
            "depth": 0.8,
            "description": "Strip foundation along container edges",
        },
        "raft": {
            "width": 25.0,
            "length": 45.0,
            "depth": 0.6,
            "description": "Raft/mat foundation for poor soil conditions",
        },
        "default": {
            "width": 20.0,
            "length": 40.0,
            "depth": 0.5,
            "description": "Default pad foundation",
        },
    }

    return foundation_specs.get(foundation_type, foundation_specs["default"])


def create_asset_footprint(
    lon: float,
    lat: float,
    foundation_type: str,
    rotation: float = 0.0,
) -> Polygon:
    """
    Create a polygon footprint for an asset at the given location.

    Args:
        lon: Longitude of asset center
        lat: Latitude of asset center
        foundation_type: Type of foundation
        rotation: Rotation angle in degrees (clockwise from north)

    Returns:
        Shapely Polygon representing the asset footprint
    """
    specs = get_foundation_dimensions(foundation_type)
    width = specs["width"]
    length = specs["length"]

    # Convert dimensions to degrees
    half_width_deg = meters_to_degrees(width / 2, lat)
    half_length_deg = meters_to_degrees(length / 2, lat)

    # Create rectangle corners (before rotation)
    corners = [
        (-half_width_deg, -half_length_deg),
        (half_width_deg, -half_length_deg),
        (half_width_deg, half_length_deg),
        (-half_width_deg, half_length_deg),
    ]

    # Apply rotation if specified
    if rotation != 0:
        angle_rad = np.radians(rotation)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
        rotated_corners = []
        for dx, dy in corners:
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a
            rotated_corners.append((rx, ry))
        corners = rotated_corners

    # Translate to asset position
    polygon_coords = [(lon + dx, lat + dy) for dx, dy in corners]
    polygon_coords.append(polygon_coords[0])  # Close the polygon

    return Polygon(polygon_coords)


def calculate_asset_volume(
    lon: float,
    lat: float,
    foundation_type: str,
    dem_path: str,
    grid_resolution: float,
    rotation: float = 0.0,
    design_elevation: Optional[float] = None,
) -> AssetVolumeResult:
    """
    Calculate cut/fill volume for a single asset.

    Args:
        lon: Longitude of asset center
        lat: Latitude of asset center
        foundation_type: Type of foundation (pad, pier, strip, raft)
        dem_path: Path to DEM raster file
        grid_resolution: Grid resolution in meters
        rotation: Asset rotation in degrees
        design_elevation: Target elevation (if None, uses average existing)

    Returns:
        AssetVolumeResult with volume calculations
    """
    specs = get_foundation_dimensions(foundation_type)
    footprint = create_asset_footprint(lon, lat, foundation_type, rotation)
    footprint_bounds = footprint.bounds

    # Calculate grid cell area in square meters
    cell_size_deg = meters_to_degrees(grid_resolution, lat)
    cell_area_m2 = grid_resolution * grid_resolution

    # Sample elevation within footprint
    elevations = []
    grid_cells = 0

    try:
        with rasterio.open(dem_path) as src:
            nodata = src.nodata

            # Generate grid points within footprint
            minx, miny, maxx, maxy = footprint_bounds
            x_coords = np.arange(minx, maxx, cell_size_deg)
            y_coords = np.arange(miny, maxy, cell_size_deg)

            for y in y_coords:
                for x in x_coords:
                    point = Point(x, y)
                    if footprint.contains(point):
                        values = list(src.sample([(x, y)]))
                        if values and len(values[0]) > 0:
                            elev = values[0][0]
                            valid = nodata is None or (
                                not np.isnan(elev) and elev != nodata
                            )
                            if valid:
                                elevations.append(float(elev))
                                grid_cells += 1

    except Exception as e:
        logger.error(f"Error sampling elevation for asset: {e}")
        return AssetVolumeResult(
            asset_id=0,
            position=(lon, lat),
            foundation_type=foundation_type,
        )

    if not elevations:
        logger.warning(f"No elevation data found for asset at ({lon}, {lat})")
        return AssetVolumeResult(
            asset_id=0,
            position=(lon, lat),
            foundation_type=foundation_type,
        )

    elevations_arr = np.array(elevations)
    avg_elevation = float(np.mean(elevations_arr))

    # Determine design elevation
    if design_elevation is None:
        # Use slightly above average to minimize cut/fill
        design_elevation = avg_elevation

    # Calculate cut and fill for each cell
    cut_depths = []
    fill_depths = []

    for elev in elevations:
        # Account for foundation depth
        target_elev = design_elevation - specs["depth"]
        diff = elev - target_elev

        if diff > 0:  # Need to cut (excavate)
            cut_depths.append(diff)
        else:  # Need to fill
            fill_depths.append(abs(diff))

    # Calculate volumes
    cut_volume = sum(cut_depths) * cell_area_m2
    fill_volume = sum(fill_depths) * cell_area_m2

    # Calculate footprint area
    footprint_area = footprint.area * (degrees_to_meters(1, lat) ** 2)

    return AssetVolumeResult(
        asset_id=0,  # Will be set by caller
        position=(lon, lat),
        foundation_type=foundation_type,
        cut_volume_m3=cut_volume,
        fill_volume_m3=fill_volume,
        net_volume_m3=cut_volume - fill_volume,
        footprint_area_m2=footprint_area,
        avg_existing_elevation=avg_elevation,
        design_elevation=design_elevation,
        max_cut_depth=max(cut_depths) if cut_depths else 0.0,
        max_fill_depth=max(fill_depths) if fill_depths else 0.0,
        grid_cells_analyzed=grid_cells,
    )


def create_road_corridor(
    coordinates: list[list[float]],
    road_width: float,
) -> Optional[Polygon]:
    """
    Create a polygon representing the road corridor.

    Args:
        coordinates: List of [lon, lat, elev] coordinates
        road_width: Road width in meters

    Returns:
        Shapely Polygon representing the road corridor
    """
    if len(coordinates) < 2:
        return None

    # Create centerline
    centerline = LineString([(c[0], c[1]) for c in coordinates])

    # Buffer to create corridor
    center_lat = (coordinates[0][1] + coordinates[-1][1]) / 2
    buffer_deg = meters_to_degrees(road_width / 2, center_lat)

    corridor = centerline.buffer(buffer_deg, cap_style=2)  # Flat caps
    return corridor if isinstance(corridor, Polygon) else None


def calculate_road_segment_volume(
    coordinates: list[list[float]],
    road_width: float,
    dem_path: str,
    grid_resolution: float,
    design_grade: Optional[float] = None,
) -> RoadSegmentVolumeResult:
    """
    Calculate cut/fill volume for a road segment.

    Args:
        coordinates: List of [lon, lat, elev] coordinates along road centerline
        road_width: Road width in meters
        dem_path: Path to DEM raster file
        grid_resolution: Grid resolution in meters
        design_grade: Target grade percentage (if None, follows terrain)

    Returns:
        RoadSegmentVolumeResult with volume calculations
    """
    if len(coordinates) < 2:
        return RoadSegmentVolumeResult(segment_id=0, from_asset=0, to_asset=0)

    corridor = create_road_corridor(coordinates, road_width)
    if corridor is None:
        return RoadSegmentVolumeResult(segment_id=0, from_asset=0, to_asset=0)

    corridor_bounds = corridor.bounds
    center_lat = (coordinates[0][1] + coordinates[-1][1]) / 2

    # Calculate grid cell size
    cell_size_deg = meters_to_degrees(grid_resolution, center_lat)
    cell_area_m2 = grid_resolution * grid_resolution

    # Calculate road length
    road_length = 0.0
    for i in range(len(coordinates) - 1):
        road_length += haversine_distance(
            coordinates[i][0],
            coordinates[i][1],
            coordinates[i + 1][0],
            coordinates[i + 1][1],
        )

    # Create centerline for interpolation
    centerline = LineString([(c[0], c[1]) for c in coordinates])
    design_elevations = [c[2] for c in coordinates]

    cut_depths = []
    fill_depths = []
    grid_cells = 0

    try:
        with rasterio.open(dem_path) as src:
            nodata = src.nodata

            # Generate grid points within corridor
            minx, miny, maxx, maxy = corridor_bounds
            x_coords = np.arange(minx, maxx, cell_size_deg)
            y_coords = np.arange(miny, maxy, cell_size_deg)

            for y in y_coords:
                for x in x_coords:
                    point = Point(x, y)
                    if corridor.contains(point):
                        # Sample existing elevation
                        values = list(src.sample([(x, y)]))
                        if values and len(values[0]) > 0:
                            existing_elev = values[0][0]
                            if nodata is None or (
                                not np.isnan(existing_elev) and existing_elev != nodata
                            ):
                                # Interpolate design elevation along centerline
                                proj_dist = centerline.project(point)
                                total_length = centerline.length

                                if total_length > 0:
                                    # Linear interpolation of design elevation
                                    ratio = proj_dist / total_length
                                    idx = min(
                                        int(ratio * (len(design_elevations) - 1)),
                                        len(design_elevations) - 2,
                                    )
                                    local_ratio = (
                                        ratio * (len(design_elevations) - 1) - idx
                                    )
                                    elev_diff = (
                                        design_elevations[idx + 1]
                                        - design_elevations[idx]
                                    )
                                    design_elev = (
                                        design_elevations[idx] + local_ratio * elev_diff
                                    )

                                    # Calculate difference (road surface at grade)
                                    diff = existing_elev - design_elev

                                    if diff > 0:  # Cut needed
                                        cut_depths.append(diff)
                                    else:  # Fill needed
                                        fill_depths.append(abs(diff))

                                    grid_cells += 1

    except Exception as e:
        logger.error(f"Error calculating road segment volume: {e}")
        return RoadSegmentVolumeResult(segment_id=0, from_asset=0, to_asset=0)

    # Calculate volumes
    cut_volume = sum(cut_depths) * cell_area_m2
    fill_volume = sum(fill_depths) * cell_area_m2
    road_area = road_length * road_width

    return RoadSegmentVolumeResult(
        segment_id=0,  # Will be set by caller
        from_asset=0,
        to_asset=0,
        cut_volume_m3=cut_volume,
        fill_volume_m3=fill_volume,
        net_volume_m3=cut_volume - fill_volume,
        road_length_m=road_length,
        road_area_m2=road_area,
        avg_cut_depth=float(np.mean(cut_depths)) if cut_depths else 0.0,
        avg_fill_depth=float(np.mean(fill_depths)) if fill_depths else 0.0,
        max_cut_depth=max(cut_depths) if cut_depths else 0.0,
        max_fill_depth=max(fill_depths) if fill_depths else 0.0,
        grid_cells_analyzed=grid_cells,
    )


def generate_visualization_data(
    asset_volumes: list[AssetVolumeResult],
    road_volumes: list[RoadSegmentVolumeResult],
    dem_path: str,
    bounds: tuple[float, float, float, float],
    grid_resolution: float,
) -> dict[str, Any]:
    """
    Generate grid data for 3D visualization of cut/fill areas.

    Returns:
        Dictionary with grid data for visualization
    """
    minx, miny, maxx, maxy = bounds
    center_lat = (miny + maxy) / 2
    cell_size_deg = meters_to_degrees(grid_resolution, center_lat)

    x_coords = np.arange(minx, maxx, cell_size_deg)
    y_coords = np.arange(miny, maxy, cell_size_deg)

    grid_width = len(x_coords)
    grid_height = len(y_coords)

    # This is a simplified visualization data structure
    # In production, you would sample the actual cut/fill depths at each grid cell
    visualization_data = {
        "bounds": {
            "minx": minx,
            "miny": miny,
            "maxx": maxx,
            "maxy": maxy,
        },
        "grid_resolution": grid_resolution,
        "grid_width": grid_width,
        "grid_height": grid_height,
        "assets": [
            {
                "id": av.asset_id,
                "position": av.position,
                "cut_volume": av.cut_volume_m3,
                "fill_volume": av.fill_volume_m3,
                "footprint_area": av.footprint_area_m2,
            }
            for av in asset_volumes
        ],
        "roads": [
            {
                "id": rv.segment_id,
                "cut_volume": rv.cut_volume_m3,
                "fill_volume": rv.fill_volume_m3,
                "length": rv.road_length_m,
            }
            for rv in road_volumes
        ],
    }

    return visualization_data


def estimate_volumes(
    asset_positions: list[dict[str, Any]],
    road_segments: Optional[list[dict[str, Any]]],
    dem_path: str,
    grid_resolution: float,
    foundation_type: str = "pad",
    road_width: float = 6.0,
    include_visualization: bool = True,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> VolumeEstimationResult:
    """
    Main function to estimate cut/fill volumes for assets and roads.

    Args:
        asset_positions: List of asset dicts with position, id, foundation_type
        road_segments: Optional list of road segment dicts with coordinates
        dem_path: Path to DEM raster file
        grid_resolution: Grid resolution in meters (1-10m)
        foundation_type: Default foundation type for assets
        road_width: Road width in meters
        include_visualization: Whether to generate visualization data
        progress_callback: Optional callback for progress updates

    Returns:
        VolumeEstimationResult with all volume calculations
    """
    start_time = time.time()
    progress = ProgressTracker(callback=progress_callback)

    try:
        # Validate inputs
        if not asset_positions and not road_segments:
            return VolumeEstimationResult(
                success=False,
                error_message="No assets or roads provided for volume estimation",
            )

        if grid_resolution < 1 or grid_resolution > 10:
            grid_resolution = max(1, min(10, grid_resolution))
            logger.warning(f"Grid resolution clamped to {grid_resolution}m")

        # Step 1: Validate DEM
        progress.update(1, "Validating terrain data")
        try:
            with rasterio.open(dem_path) as src:
                dem_resolution = abs(src.transform[0])
                if src.crs.is_geographic:
                    center_lat = (src.bounds.bottom + src.bounds.top) / 2
                    lat_scale = np.cos(np.radians(center_lat))
                    dem_resolution = dem_resolution * 111320 * lat_scale
        except Exception as e:
            return VolumeEstimationResult(
                success=False,
                error_message=f"Failed to read DEM file: {str(e)}",
            )

        # Step 2: Calculate asset volumes
        progress.update(2, "Calculating asset volumes")
        asset_volumes = []
        total_asset_cut = 0.0
        total_asset_fill = 0.0
        total_cells = 0

        for i, asset in enumerate(asset_positions):
            pos = asset.get("position", [0, 0])
            lon, lat = pos[0], pos[1]
            asset_id = asset.get("id", i + 1)
            asset_foundation = asset.get("foundation_type", foundation_type)
            rotation = asset.get("rotation", 0.0)

            result = calculate_asset_volume(
                lon=lon,
                lat=lat,
                foundation_type=asset_foundation,
                dem_path=dem_path,
                grid_resolution=grid_resolution,
                rotation=rotation,
            )
            result.asset_id = asset_id
            asset_volumes.append(result)

            total_asset_cut += result.cut_volume_m3
            total_asset_fill += result.fill_volume_m3
            total_cells += result.grid_cells_analyzed

        # Step 3: Calculate road volumes
        progress.update(3, "Calculating road volumes")
        road_volumes: list[RoadSegmentVolumeResult] = []
        total_road_cut = 0.0
        total_road_fill = 0.0

        if road_segments:
            for i, segment in enumerate(road_segments):
                coords = segment.get("coordinates", [])
                if len(coords) < 2:
                    continue

                road_result = calculate_road_segment_volume(
                    coordinates=coords,
                    road_width=road_width,
                    dem_path=dem_path,
                    grid_resolution=grid_resolution,
                )
                road_result.segment_id = segment.get("id", i + 1)
                road_result.from_asset = segment.get("from_node", 0)
                road_result.to_asset = segment.get("to_node", 0)
                road_volumes.append(road_result)

                total_road_cut += road_result.cut_volume_m3
                total_road_fill += road_result.fill_volume_m3
                total_cells += road_result.grid_cells_analyzed

        # Step 4: Calculate totals
        progress.update(4, "Calculating project totals")
        total_cut = total_asset_cut + total_road_cut
        total_fill = total_asset_fill + total_road_fill
        total_net = total_cut - total_fill
        cut_fill_ratio = total_cut / total_fill if total_fill > 0 else 0.0

        # Step 5: Generate visualization data
        progress.update(5, "Generating visualization data")
        visualization_data = None

        if include_visualization and (asset_volumes or road_volumes):
            # Calculate bounds from all assets and roads
            all_lons = []
            all_lats = []

            for av in asset_volumes:
                all_lons.append(av.position[0])
                all_lats.append(av.position[1])

            if road_segments:
                for seg in road_segments:
                    for coord in seg.get("coordinates", []):
                        all_lons.append(coord[0])
                        all_lats.append(coord[1])

            if all_lons and all_lats:
                padding = 0.001  # Small padding in degrees
                bounds = (
                    min(all_lons) - padding,
                    min(all_lats) - padding,
                    max(all_lons) + padding,
                    max(all_lats) + padding,
                )
                visualization_data = generate_visualization_data(
                    asset_volumes,
                    road_volumes,
                    dem_path,
                    bounds,
                    grid_resolution,
                )

        # Step 6: Finalize
        progress.update(6, "Finalizing results")
        processing_time = time.time() - start_time

        # Estimate memory usage (rough)
        memory_mb = (total_cells * 8) / (1024 * 1024)  # 8 bytes per float

        return VolumeEstimationResult(
            success=True,
            asset_volumes=asset_volumes,
            total_asset_cut_volume_m3=total_asset_cut,
            total_asset_fill_volume_m3=total_asset_fill,
            total_asset_net_volume_m3=total_asset_cut - total_asset_fill,
            road_volumes=road_volumes,
            total_road_cut_volume_m3=total_road_cut,
            total_road_fill_volume_m3=total_road_fill,
            total_road_net_volume_m3=total_road_cut - total_road_fill,
            total_cut_volume_m3=total_cut,
            total_fill_volume_m3=total_fill,
            total_net_volume_m3=total_net,
            cut_fill_ratio=cut_fill_ratio,
            visualization_data=visualization_data,
            dem_resolution=dem_resolution,
            grid_cell_size=grid_resolution,
            total_cells_analyzed=total_cells,
            processing_time=processing_time,
            memory_peak_mb=memory_mb,
        )

    except Exception as e:
        logger.exception("Error during volume estimation")
        return VolumeEstimationResult(
            success=False,
            error_message=f"Volume estimation failed: {str(e)}",
            processing_time=time.time() - start_time,
        )


def generate_volumetric_report(
    result: VolumeEstimationResult,
    project_name: str = "Untitled Project",
) -> dict[str, Any]:
    """
    Generate a detailed volumetric report from the estimation result.

    Returns:
        Dictionary containing the formatted report data
    """
    if not result.success:
        return {
            "success": False,
            "error": result.error_message,
        }

    report = {
        "project_name": project_name,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_cut_volume_m3": round(result.total_cut_volume_m3, 2),
            "total_fill_volume_m3": round(result.total_fill_volume_m3, 2),
            "total_net_volume_m3": round(result.total_net_volume_m3, 2),
            "cut_fill_ratio": round(result.cut_fill_ratio, 3),
            "balance_status": (
                "Balanced"
                if 0.8 <= result.cut_fill_ratio <= 1.2
                else ("Excess Cut" if result.cut_fill_ratio > 1.2 else "Excess Fill")
            ),
        },
        "asset_breakdown": {
            "total_assets": len(result.asset_volumes),
            "total_cut_volume_m3": round(result.total_asset_cut_volume_m3, 2),
            "total_fill_volume_m3": round(result.total_asset_fill_volume_m3, 2),
            "assets": [
                {
                    "id": av.asset_id,
                    "foundation_type": av.foundation_type,
                    "position": {
                        "longitude": round(av.position[0], 6),
                        "latitude": round(av.position[1], 6),
                    },
                    "cut_volume_m3": round(av.cut_volume_m3, 2),
                    "fill_volume_m3": round(av.fill_volume_m3, 2),
                    "net_volume_m3": round(av.net_volume_m3, 2),
                    "footprint_area_m2": round(av.footprint_area_m2, 2),
                    "max_cut_depth_m": round(av.max_cut_depth, 2),
                    "max_fill_depth_m": round(av.max_fill_depth, 2),
                }
                for av in result.asset_volumes
            ],
        },
        "road_breakdown": {
            "total_segments": len(result.road_volumes),
            "total_cut_volume_m3": round(result.total_road_cut_volume_m3, 2),
            "total_fill_volume_m3": round(result.total_road_fill_volume_m3, 2),
            "segments": [
                {
                    "id": rv.segment_id,
                    "from_asset": rv.from_asset,
                    "to_asset": rv.to_asset,
                    "length_m": round(rv.road_length_m, 2),
                    "area_m2": round(rv.road_area_m2, 2),
                    "cut_volume_m3": round(rv.cut_volume_m3, 2),
                    "fill_volume_m3": round(rv.fill_volume_m3, 2),
                    "net_volume_m3": round(rv.net_volume_m3, 2),
                    "avg_cut_depth_m": round(rv.avg_cut_depth, 2),
                    "avg_fill_depth_m": round(rv.avg_fill_depth, 2),
                }
                for rv in result.road_volumes
            ],
        },
        "processing_metadata": {
            "dem_resolution_m": round(result.dem_resolution, 2),
            "grid_cell_size_m": result.grid_cell_size,
            "total_cells_analyzed": result.total_cells_analyzed,
            "processing_time_seconds": round(result.processing_time, 2),
            "memory_peak_mb": round(result.memory_peak_mb, 2),
        },
    }

    return report
