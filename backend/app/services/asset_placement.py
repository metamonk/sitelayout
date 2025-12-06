"""
Asset Auto-Placement Engine for BESS (Battery Energy Storage System).

This service provides grid-based optimization for placing assets with constraints
on terrain slope, exclusion zones, and configurable optimization criteria.
"""

import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import rasterio
from scipy.spatial import distance_matrix  # type: ignore[import-untyped]
from shapely.geometry import Point, Polygon, shape

logger = logging.getLogger("sitelayout.asset_placement")


@dataclass
class ProgressTracker:
    """Tracks progress of asset placement."""

    total_steps: int = 5
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
class GridCell:
    """Represents a single grid cell."""

    x: float  # Longitude
    y: float  # Latitude
    row: int
    col: int
    elevation: Optional[float] = None
    slope: Optional[float] = None
    is_valid: bool = False
    exclusion_score: float = 0.0  # 0 = not excluded, 1 = fully excluded


@dataclass
class PlacementResult:
    """Result of asset placement operation."""

    success: bool
    placed_positions: list[tuple[float, float]] = field(default_factory=list)
    placement_details: dict[str, Any] = field(default_factory=dict)
    assets_placed: int = 0
    placement_success_rate: float = 0.0
    grid_cells_total: int = 0
    grid_cells_valid: int = 0
    grid_cells_excluded: int = 0
    avg_slope: Optional[float] = None
    avg_inter_asset_distance: Optional[float] = None
    total_cut_fill_volume: Optional[float] = None
    processing_time: float = 0.0
    memory_peak_mb: float = 0.0
    algorithm_iterations: int = 0
    error_message: Optional[str] = None


def generate_grid(
    bounds: tuple[float, float, float, float],
    resolution: float,
) -> list[GridCell]:
    """
    Generate a regular grid of candidate locations.

    Args:
        bounds: Bounding box (minx, miny, maxx, maxy) in WGS84
        resolution: Grid cell size in meters

    Returns:
        List of GridCell objects
    """
    minx, miny, maxx, maxy = bounds

    # Convert resolution from meters to degrees (rough approximation)
    # At the equator, 1 degree = ~111km
    center_lat = (miny + maxy) / 2
    meters_per_degree_lat = 111320
    meters_per_degree_lon = 111320 * np.cos(np.radians(center_lat))

    dx = resolution / meters_per_degree_lon
    dy = resolution / meters_per_degree_lat

    # Generate grid points
    x_coords = np.arange(minx, maxx, dx)
    y_coords = np.arange(miny, maxy, dy)

    cells = []
    for row, y in enumerate(y_coords):
        for col, x in enumerate(x_coords):
            cells.append(GridCell(x=x, y=y, row=row, col=col))

    return cells


def load_terrain_data(
    cells: list[GridCell],
    slope_raster_path: Optional[str],
) -> None:
    """
    Load terrain data (elevation and slope) for grid cells.

    Args:
        cells: List of grid cells to populate with terrain data
        slope_raster_path: Path to slope raster file
    """
    if not slope_raster_path:
        logger.warning("No slope raster provided, all slopes set to 0")
        for cell in cells:
            cell.slope = 0.0
        return

    try:
        with rasterio.open(slope_raster_path) as src:
            for cell in cells:
                # Sample the raster at the cell center
                values = list(src.sample([(cell.x, cell.y)]))
                if values:
                    slope_value = values[0][0]
                    if not np.isnan(slope_value) and slope_value != src.nodata:
                        cell.slope = float(slope_value)
                    else:
                        cell.slope = None
                else:
                    cell.slope = None
    except Exception as e:
        logger.error(f"Error loading terrain data: {e}")
        for cell in cells:
            cell.slope = None


def apply_constraints(
    cells: list[GridCell],
    max_slope: float,
    exclusion_zones: list[dict[str, Any]],
    placement_area: Optional[Polygon] = None,
) -> None:
    """
    Apply constraints to filter valid grid cells.

    Args:
        cells: List of grid cells
        max_slope: Maximum allowed slope in degrees
        exclusion_zones: List of exclusion zone geometries (GeoJSON)
        placement_area: Optional polygon defining placement area
    """
    # Convert exclusion zones to Shapely geometries
    exclusion_geoms = []
    for zone in exclusion_zones:
        try:
            geom = shape(zone)
            exclusion_geoms.append(geom)
        except Exception as e:
            logger.warning(f"Error parsing exclusion zone: {e}")

    # Apply constraints
    for cell in cells:
        cell.is_valid = True

        # Check slope constraint
        if cell.slope is None or cell.slope > max_slope:
            cell.is_valid = False
            continue

        # Create point for spatial checks
        point = Point(cell.x, cell.y)

        # Check placement area constraint
        if placement_area and not placement_area.contains(point):
            cell.is_valid = False
            continue

        # Check exclusion zones
        for excl_geom in exclusion_geoms:
            if excl_geom.contains(point):
                cell.is_valid = False
                cell.exclusion_score = 1.0
                break


def calculate_scores(
    cells: list[GridCell],
    optimization_criteria: str,
) -> np.ndarray:
    """
    Calculate optimization scores for valid cells.

    Args:
        cells: List of grid cells
        optimization_criteria: Type of optimization to perform

    Returns:
        Array of scores (lower is better)
    """
    valid_cells = [c for c in cells if c.is_valid]
    if not valid_cells:
        return np.array([])

    scores = np.zeros(len(valid_cells))

    if optimization_criteria == "maximize_flat_areas":
        # Lower slope is better
        for i, cell in enumerate(valid_cells):
            scores[i] = cell.slope if cell.slope is not None else 999

    elif optimization_criteria == "minimize_cut_fill":
        # Prefer areas with consistent elevation
        # Use slope as a proxy (flatter = less cut/fill)
        for i, cell in enumerate(valid_cells):
            scores[i] = cell.slope if cell.slope is not None else 999

    elif optimization_criteria == "balanced":
        # Balanced scoring combining multiple factors
        for i, cell in enumerate(valid_cells):
            slope_score = cell.slope if cell.slope is not None else 999
            # Normalize and combine
            scores[i] = slope_score

    else:  # minimize_inter_asset_distance will be handled differently
        # Default: prefer flatter areas
        for i, cell in enumerate(valid_cells):
            scores[i] = cell.slope if cell.slope is not None else 999

    return scores


def select_optimal_locations(
    cells: list[GridCell],
    num_assets: int,
    min_spacing: float,
    optimization_criteria: str,
) -> list[GridCell]:
    """
    Select optimal locations for assets using optimization.

    Args:
        cells: List of grid cells
        num_assets: Number of assets to place
        min_spacing: Minimum spacing between assets in meters
        optimization_criteria: Optimization strategy

    Returns:
        List of selected grid cells
    """
    valid_cells = [c for c in cells if c.is_valid]

    if len(valid_cells) == 0:
        logger.warning("No valid cells available for placement")
        return []

    if len(valid_cells) <= num_assets:
        logger.warning(
            f"Only {len(valid_cells)} valid cells available for {num_assets} assets"
        )
        return valid_cells

    # Calculate scores for all valid cells
    scores = calculate_scores(valid_cells, optimization_criteria)

    # If optimizing for minimum inter-asset distance, use clustering approach
    if optimization_criteria == "minimize_inter_asset_distance":
        return select_clustered_locations(valid_cells, num_assets, min_spacing, scores)

    # Otherwise, use greedy selection with spacing constraints
    return greedy_selection(valid_cells, num_assets, min_spacing, scores)


def greedy_selection(
    cells: list[GridCell],
    num_assets: int,
    min_spacing: float,
    scores: np.ndarray,
) -> list[GridCell]:
    """
    Greedy selection of locations with spacing constraints.

    Args:
        cells: Valid grid cells
        num_assets: Number of assets to select
        min_spacing: Minimum spacing in meters
        scores: Optimization scores (lower is better)

    Returns:
        Selected cells
    """
    selected: list[GridCell] = []
    remaining_indices = list(range(len(cells)))

    # Convert min_spacing from meters to degrees (rough approximation)
    min_spacing_deg = min_spacing / 111320  # At equator

    while len(selected) < num_assets and remaining_indices:
        # Find the best remaining cell
        best_idx = min(remaining_indices, key=lambda i: scores[i])
        best_cell = cells[best_idx]
        selected.append(best_cell)

        # Remove cells within min_spacing
        remaining_indices = [
            i
            for i in remaining_indices
            if i != best_idx
            and (
                abs(cells[i].x - best_cell.x) >= min_spacing_deg
                or abs(cells[i].y - best_cell.y) >= min_spacing_deg
            )
        ]

    return selected


def select_clustered_locations(
    cells: list[GridCell],
    num_assets: int,
    min_spacing: float,
    scores: np.ndarray,
) -> list[GridCell]:
    """
    Select locations that minimize total inter-asset distance.

    Uses a simple clustering approach to group assets together.

    Args:
        cells: Valid grid cells
        num_assets: Number of assets to select
        min_spacing: Minimum spacing in meters
        scores: Quality scores for each cell

    Returns:
        Selected cells
    """
    # First, select top candidates based on quality scores
    num_candidates = min(num_assets * 3, len(cells))
    candidate_indices = np.argsort(scores)[:num_candidates]
    candidates = [cells[i] for i in candidate_indices]

    # Convert to coordinate array
    coords = np.array([[c.x, c.y] for c in candidates])

    # Calculate pairwise distances
    distances = distance_matrix(coords, coords)

    # Convert min_spacing to degrees
    min_spacing_deg = min_spacing / 111320

    # Greedy selection favoring proximity to already selected points
    selected_indices = []
    remaining_indices = list(range(len(candidates)))

    # Start with the best quality cell
    first_idx = 0
    selected_indices.append(first_idx)
    remaining_indices.remove(first_idx)

    while len(selected_indices) < num_assets and remaining_indices:
        # Find the closest cell to the centroid of selected cells that meets spacing
        centroid = np.mean(coords[selected_indices], axis=0)

        best_idx = None
        best_distance = float("inf")

        for idx in remaining_indices:
            # Check spacing constraint with all selected cells
            min_dist = min(distances[idx][sel_idx] for sel_idx in selected_indices)
            if min_dist >= min_spacing_deg:
                dist_to_centroid = float(np.linalg.norm(coords[idx] - centroid))
                if dist_to_centroid < best_distance:
                    best_distance = dist_to_centroid
                    best_idx = idx

        if best_idx is None:
            # No valid cells remaining, break
            break

        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)

    return [candidates[i] for i in selected_indices]


def calculate_placement_metrics(
    selected_cells: list[GridCell],
) -> dict[str, Any]:
    """
    Calculate metrics for the placement.

    Args:
        selected_cells: List of selected grid cells

    Returns:
        Dictionary of metrics
    """
    if not selected_cells:
        return {
            "avg_slope": None,
            "avg_inter_asset_distance": None,
            "total_cut_fill_volume": None,
        }

    # Average slope
    slopes = [c.slope for c in selected_cells if c.slope is not None]
    avg_slope = float(np.mean(slopes)) if slopes else None

    # Average inter-asset distance
    if len(selected_cells) > 1:
        coords = np.array([[c.x, c.y] for c in selected_cells])
        distances = distance_matrix(coords, coords)
        # Get upper triangle (excluding diagonal)
        upper_tri = distances[np.triu_indices_from(distances, k=1)]
        avg_distance_deg = float(np.mean(upper_tri))
        # Convert to meters (rough approximation)
        avg_inter_asset_distance = avg_distance_deg * 111320
    else:
        avg_inter_asset_distance = None

    # Total cut/fill volume (placeholder - would need detailed elevation analysis)
    total_cut_fill_volume = None

    return {
        "avg_slope": avg_slope,
        "avg_inter_asset_distance": avg_inter_asset_distance,
        "total_cut_fill_volume": total_cut_fill_volume,
    }


def place_assets(
    placement_area: dict[str, Any],
    num_assets: int,
    grid_resolution: float,
    min_spacing: float,
    max_slope: float,
    optimization_criteria: str,
    slope_raster_path: Optional[str] = None,
    exclusion_zones: Optional[list[dict[str, Any]]] = None,
    advanced_settings: Optional[dict[str, Any]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> PlacementResult:
    """
    Main function to place assets using grid-based optimization.

    Args:
        placement_area: GeoJSON polygon defining placement area
        num_assets: Number of assets to place
        grid_resolution: Grid cell size in meters
        min_spacing: Minimum spacing between assets in meters
        max_slope: Maximum allowed slope in degrees
        optimization_criteria: Type of optimization
        slope_raster_path: Optional path to slope raster
        exclusion_zones: Optional list of exclusion zone geometries
        advanced_settings: Optional advanced configuration
        progress_callback: Optional callback for progress updates

    Returns:
        PlacementResult object
    """
    start_time = time.time()
    progress = ProgressTracker(callback=progress_callback)

    try:
        # Step 1: Parse placement area
        progress.update(1, "Parsing placement area")
        placement_geom = shape(placement_area)
        bounds = placement_geom.bounds  # (minx, miny, maxx, maxy)

        # Step 2: Generate grid
        progress.update(2, "Generating candidate grid")
        cells = generate_grid(bounds, grid_resolution)
        logger.info(f"Generated {len(cells)} grid cells")

        # Step 3: Load terrain data
        progress.update(3, "Loading terrain data")
        load_terrain_data(cells, slope_raster_path)

        # Step 4: Apply constraints
        progress.update(4, "Applying constraints")
        apply_constraints(
            cells,
            max_slope,
            exclusion_zones or [],
            placement_geom if isinstance(placement_geom, Polygon) else None,
        )

        valid_cells = [c for c in cells if c.is_valid]
        excluded_cells = len(cells) - len(valid_cells)
        logger.info(f"Valid cells: {len(valid_cells)}, Excluded: {excluded_cells}")

        # Step 5: Select optimal locations
        progress.update(5, "Optimizing asset placement")
        selected_cells = select_optimal_locations(
            cells,
            num_assets,
            min_spacing,
            optimization_criteria,
        )

        # Calculate metrics
        metrics = calculate_placement_metrics(selected_cells)

        # Format results
        placed_positions = [(c.x, c.y) for c in selected_cells]
        placement_details = {
            "assets": [
                {
                    "id": i + 1,
                    "position": [c.x, c.y],
                    "elevation": c.elevation,
                    "slope": c.slope,
                    "rotation": 0.0,  # Default rotation
                    "score": c.slope if c.slope is not None else 0.0,
                }
                for i, c in enumerate(selected_cells)
            ]
        }

        processing_time = time.time() - start_time
        assets_placed = len(selected_cells)
        placement_success_rate = (
            (assets_placed / num_assets * 100) if num_assets > 0 else 0
        )

        return PlacementResult(
            success=True,
            placed_positions=placed_positions,
            placement_details=placement_details,
            assets_placed=assets_placed,
            placement_success_rate=placement_success_rate,
            grid_cells_total=len(cells),
            grid_cells_valid=len(valid_cells),
            grid_cells_excluded=excluded_cells,
            avg_slope=metrics["avg_slope"],
            avg_inter_asset_distance=metrics["avg_inter_asset_distance"],
            total_cut_fill_volume=metrics["total_cut_fill_volume"],
            processing_time=processing_time,
            memory_peak_mb=0.0,  # Placeholder
            algorithm_iterations=1,  # Placeholder
        )

    except Exception as e:
        logger.exception("Error during asset placement")
        return PlacementResult(
            success=False,
            error_message=f"Asset placement failed: {str(e)}\n{traceback.format_exc()}",
            processing_time=time.time() - start_time,
        )
