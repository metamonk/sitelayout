"""
Road Network Generation Service.

This service generates road networks connecting placed assets using
terrain-aware A* pathfinding with grade constraints.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import networkx as nx  # type: ignore[import-untyped]
import numpy as np
import rasterio
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import unary_union

logger = logging.getLogger("sitelayout.road_network")

# Default constants
EARTH_RADIUS_M = 6371000  # Earth radius in meters
METERS_PER_DEGREE_LAT = 111320  # Approximate meters per degree latitude


@dataclass
class ProgressTracker:
    """Tracks progress of road network generation."""

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
class GridNode:
    """Represents a node in the pathfinding grid."""

    x: float  # Longitude
    y: float  # Latitude
    row: int
    col: int
    elevation: Optional[float] = None
    slope: Optional[float] = None
    is_valid: bool = True  # Not in exclusion zone


@dataclass
class RoadSegment:
    """Represents a single road segment."""

    id: int
    from_node: int  # Asset/intersection ID
    to_node: int  # Asset/intersection ID
    coordinates: list[list[float]]  # [[lon, lat, elev], ...]
    length_m: float = 0.0
    avg_grade: float = 0.0
    max_grade: float = 0.0
    cut_volume: float = 0.0
    fill_volume: float = 0.0


@dataclass
class RoadNetworkResult:
    """Result of road network generation."""

    success: bool
    road_centerlines: Optional[list[list[list[float]]]] = (
        None  # [[[lon, lat], ...], ...]
    )
    road_polygons: Optional[Any] = None  # Shapely MultiPolygon
    road_details: dict[str, Any] = field(default_factory=dict)

    # Statistics
    total_road_length: float = 0.0
    total_segments: int = 0
    total_intersections: int = 0

    # Grade statistics
    avg_grade: float = 0.0
    max_grade_actual: float = 0.0
    grade_compliant: bool = True

    # Earthwork
    total_cut_volume: float = 0.0
    total_fill_volume: float = 0.0
    net_earthwork_volume: float = 0.0

    # Connectivity
    assets_connected: int = 0
    connectivity_rate: float = 0.0

    # Processing metadata
    processing_time: float = 0.0
    memory_peak_mb: float = 0.0
    algorithm_iterations: int = 0
    pathfinding_algorithm: str = "astar"

    error_message: Optional[str] = None


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great-circle distance between two points in meters."""
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_M * c


def calculate_grade(
    lon1: float, lat1: float, elev1: float, lon2: float, lat2: float, elev2: float
) -> float:
    """
    Calculate road grade (slope percentage) between two points.

    Returns:
        Grade as a percentage (rise/run * 100)
    """
    horizontal_distance = haversine_distance(lon1, lat1, lon2, lat2)
    if horizontal_distance < 0.01:  # Less than 1cm
        return 0.0

    elevation_change = abs(elev2 - elev1)
    grade = (elevation_change / horizontal_distance) * 100

    return grade


def degrees_to_meters(degrees: float, latitude: float) -> float:
    """Convert degrees to meters at a given latitude."""
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude))
    # Use average of lat and lon conversion
    return degrees * (METERS_PER_DEGREE_LAT + meters_per_degree_lon) / 2


def meters_to_degrees(meters: float, latitude: float) -> float:
    """Convert meters to degrees at a given latitude."""
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude))
    avg_meters_per_degree = (METERS_PER_DEGREE_LAT + meters_per_degree_lon) / 2
    return meters / avg_meters_per_degree


def generate_pathfinding_grid(
    bounds: tuple[float, float, float, float],
    resolution: float,
) -> tuple[list[GridNode], int, int]:
    """
    Generate a grid of nodes for pathfinding.

    Args:
        bounds: Bounding box (minx, miny, maxx, maxy) in WGS84
        resolution: Grid cell size in meters

    Returns:
        Tuple of (list of GridNodes, num_rows, num_cols)
    """
    minx, miny, maxx, maxy = bounds
    center_lat = (miny + maxy) / 2

    # Convert resolution from meters to degrees
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(center_lat))
    dx = resolution / meters_per_degree_lon
    dy = resolution / METERS_PER_DEGREE_LAT

    # Generate grid
    x_coords = np.arange(minx, maxx, dx)
    y_coords = np.arange(miny, maxy, dy)

    num_rows = len(y_coords)
    num_cols = len(x_coords)

    nodes = []
    for row, y in enumerate(y_coords):
        for col, x in enumerate(x_coords):
            nodes.append(GridNode(x=x, y=y, row=row, col=col))

    return nodes, num_rows, num_cols


def load_elevation_data(
    nodes: list[GridNode],
    dem_path: Optional[str],
) -> None:
    """Load elevation data for grid nodes from DEM raster."""
    if not dem_path:
        logger.warning("No DEM provided, using flat terrain (elevation=0)")
        for node in nodes:
            node.elevation = 0.0
        return

    try:
        with rasterio.open(dem_path) as src:
            nodata = src.nodata
            for node in nodes:
                values = list(src.sample([(node.x, node.y)]))
                if values and len(values[0]) > 0:
                    elev = values[0][0]
                    if nodata is None or (not np.isnan(elev) and elev != nodata):
                        node.elevation = float(elev)
                    else:
                        node.elevation = None
                else:
                    node.elevation = None
    except Exception as e:
        logger.error(f"Error loading elevation data: {e}")
        for node in nodes:
            node.elevation = 0.0


def mark_exclusion_zones(
    nodes: list[GridNode],
    exclusion_zones: list[dict[str, Any]],
    buffer_distance: float,
) -> None:
    """Mark nodes within exclusion zones as invalid."""
    if not exclusion_zones:
        return

    # Convert exclusion zones to Shapely geometries and buffer them
    exclusion_geoms = []
    for zone in exclusion_zones:
        try:
            geom = shape(zone)
            # Apply buffer (convert meters to degrees roughly)
            center_lat = geom.centroid.y
            buffer_deg = meters_to_degrees(buffer_distance, center_lat)
            buffered = geom.buffer(buffer_deg)
            exclusion_geoms.append(buffered)
        except Exception as e:
            logger.warning(f"Error parsing exclusion zone: {e}")

    if not exclusion_geoms:
        return

    # Combine all exclusion zones
    combined_exclusions = unary_union(exclusion_geoms)

    # Mark nodes
    for node in nodes:
        point = Point(node.x, node.y)
        if combined_exclusions.contains(point):
            node.is_valid = False


def build_graph(
    nodes: list[GridNode],
    num_rows: int,
    num_cols: int,
    max_grade: float,
    optimization_criteria: str,
) -> nx.Graph:
    """
    Build a NetworkX graph for pathfinding.

    Args:
        nodes: List of grid nodes
        num_rows: Number of rows in grid
        num_cols: Number of columns in grid
        max_grade: Maximum allowed grade percentage
        optimization_criteria: Optimization strategy

    Returns:
        NetworkX graph with weighted edges
    """
    G = nx.Graph()

    # Create node index mapping
    def node_index(row: int, col: int) -> int:
        return row * num_cols + col

    # Add nodes
    for node in nodes:
        if node.is_valid and node.elevation is not None:
            idx = node_index(node.row, node.col)
            G.add_node(idx, pos=(node.x, node.y), elevation=node.elevation)

    # Add edges (8-connectivity: up, down, left, right, and diagonals)
    directions = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),  # Cardinal
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),  # Diagonal
    ]

    for node in nodes:
        if not node.is_valid or node.elevation is None:
            continue

        idx1 = node_index(node.row, node.col)

        for dr, dc in directions:
            new_row = node.row + dr
            new_col = node.col + dc

            if 0 <= new_row < num_rows and 0 <= new_col < num_cols:
                neighbor_idx = node_index(new_row, new_col)
                neighbor = nodes[neighbor_idx]

                if not neighbor.is_valid or neighbor.elevation is None:
                    continue

                if neighbor_idx not in G.nodes:
                    continue

                # Calculate edge weight
                distance = haversine_distance(node.x, node.y, neighbor.x, neighbor.y)
                grade = calculate_grade(
                    node.x,
                    node.y,
                    node.elevation,
                    neighbor.x,
                    neighbor.y,
                    neighbor.elevation,
                )

                # Skip edges that exceed grade constraint
                if grade > max_grade:
                    continue

                # Calculate weight based on optimization criteria
                if optimization_criteria == "minimal_length":
                    weight = distance
                elif optimization_criteria == "minimal_earthwork":
                    # Higher weight for steeper slopes (more earthwork needed)
                    weight = distance * (1 + grade / 5)
                elif optimization_criteria == "minimal_grade":
                    # Much higher weight for steeper slopes
                    weight = distance * (1 + (grade / 2) ** 2)
                else:  # balanced
                    weight = distance * (1 + grade / 10)

                G.add_edge(
                    idx1, neighbor_idx, weight=weight, distance=distance, grade=grade
                )

    return G


def find_nearest_node(
    G: nx.Graph,
    nodes: list[GridNode],
    num_cols: int,
    target_lon: float,
    target_lat: float,
) -> Optional[int]:
    """Find the nearest valid graph node to a target position."""
    min_dist = float("inf")
    nearest_idx = None

    for node in nodes:
        if not node.is_valid or node.elevation is None:
            continue

        idx = node.row * num_cols + node.col
        if idx not in G.nodes:
            continue

        dist = haversine_distance(target_lon, target_lat, node.x, node.y)
        if dist < min_dist:
            min_dist = dist
            nearest_idx = idx

    return nearest_idx


def astar_path(
    G: nx.Graph,
    source: int,
    target: int,
    nodes: list[GridNode],
    num_cols: int,
) -> Optional[list[int]]:
    """
    Find shortest path using A* algorithm.

    Args:
        G: NetworkX graph
        source: Source node index
        target: Target node index
        nodes: List of grid nodes
        num_cols: Number of columns in grid

    Returns:
        List of node indices in path, or None if no path exists
    """
    if source not in G.nodes or target not in G.nodes:
        return None

    def heuristic(n1: int, n2: int) -> float:
        """Euclidean distance heuristic."""
        pos1 = G.nodes[n1]["pos"]
        pos2 = G.nodes[n2]["pos"]
        return haversine_distance(pos1[0], pos1[1], pos2[0], pos2[1])

    try:
        path = nx.astar_path(G, source, target, heuristic=heuristic, weight="weight")
        return path
    except nx.NetworkXNoPath:
        return None


def extract_path_coordinates(
    path: list[int],
    G: nx.Graph,
) -> list[list[float]]:
    """Extract coordinates from a path."""
    coords = []
    for node_idx in path:
        pos = G.nodes[node_idx]["pos"]
        elev = G.nodes[node_idx].get("elevation", 0)
        coords.append([pos[0], pos[1], elev])
    return coords


def calculate_segment_metrics(
    coords: list[list[float]],
) -> tuple[float, float, float, float, float]:
    """
    Calculate metrics for a road segment.

    Returns:
        Tuple of (length_m, avg_grade, max_grade, cut_volume, fill_volume)
    """
    if len(coords) < 2:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    total_length = 0.0
    grades = []

    for i in range(len(coords) - 1):
        lon1, lat1, elev1 = coords[i]
        lon2, lat2, elev2 = coords[i + 1]

        seg_length = haversine_distance(lon1, lat1, lon2, lat2)
        total_length += seg_length

        if seg_length > 0.01:
            grade = calculate_grade(lon1, lat1, elev1, lon2, lat2, elev2)
            grades.append(grade)

    avg_grade = float(np.mean(grades)) if grades else 0.0
    max_grade = float(np.max(grades)) if grades else 0.0

    # Estimate earthwork (simplified - assumes road width and depth)
    # This is a rough estimate; actual calculation would need road design details
    cut_volume = 0.0
    fill_volume = 0.0

    return total_length, avg_grade, max_grade, cut_volume, fill_volume


def simplify_path(
    coords: list[list[float]],
    tolerance_m: float = 2.0,
) -> list[list[float]]:
    """Simplify a path using Douglas-Peucker algorithm."""
    if len(coords) < 3:
        return coords

    # Convert to LineString and simplify
    line = LineString([(c[0], c[1]) for c in coords])
    center_lat = (coords[0][1] + coords[-1][1]) / 2
    tolerance_deg = meters_to_degrees(tolerance_m, center_lat)
    simplified = line.simplify(tolerance_deg, preserve_topology=True)

    # Rebuild coordinates with elevation
    simplified_coords = list(simplified.coords)
    result = []

    for sx, sy in simplified_coords:
        # Find closest original point to get elevation
        min_dist = float("inf")
        best_elev = coords[0][2]
        for c in coords:
            dist = abs(c[0] - sx) + abs(c[1] - sy)
            if dist < min_dist:
                min_dist = dist
                best_elev = c[2]
        result.append([sx, sy, best_elev])

    return result


def create_road_polygon(
    centerline: list[list[float]],
    road_width: float,
) -> Optional[Polygon]:
    """Create a polygon representing the road with specified width."""
    if len(centerline) < 2:
        return None

    line = LineString([(c[0], c[1]) for c in centerline])
    center_lat = (centerline[0][1] + centerline[-1][1]) / 2
    buffer_deg = meters_to_degrees(road_width / 2, center_lat)

    return line.buffer(buffer_deg, cap_style=2)  # Flat caps


def build_minimum_spanning_tree(
    asset_positions: list[tuple[float, float]],
    G: nx.Graph,
    nodes: list[GridNode],
    num_cols: int,
) -> list[tuple[int, int]]:
    """
    Build a minimum spanning tree connecting all assets.

    Returns:
        List of (asset_idx1, asset_idx2) pairs representing edges in MST
    """
    n = len(asset_positions)
    if n < 2:
        return []

    # Find nearest graph nodes for each asset
    asset_nodes = []
    for lon, lat in asset_positions:
        node_idx = find_nearest_node(G, nodes, num_cols, lon, lat)
        asset_nodes.append(node_idx)

    # Build complete graph of assets with distances
    asset_graph = nx.Graph()
    for i in range(n):
        asset_graph.add_node(i)

    for i in range(n):
        for j in range(i + 1, n):
            lon1, lat1 = asset_positions[i]
            lon2, lat2 = asset_positions[j]
            dist = haversine_distance(lon1, lat1, lon2, lat2)
            asset_graph.add_edge(i, j, weight=dist)

    # Get MST
    mst = nx.minimum_spanning_tree(asset_graph)
    return list(mst.edges())


def generate_road_network(
    asset_positions: list[tuple[float, float]],
    entry_point: Optional[tuple[float, float]],
    road_width: float,
    max_grade: float,
    min_curve_radius: float,
    grid_resolution: float,
    optimization_criteria: str,
    exclusion_buffer: float,
    dem_path: Optional[str] = None,
    exclusion_zones: Optional[list[dict[str, Any]]] = None,
    advanced_settings: Optional[dict[str, Any]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> RoadNetworkResult:
    """
    Main function to generate road network connecting assets.

    Args:
        asset_positions: List of (longitude, latitude) tuples for placed assets
        entry_point: Optional (longitude, latitude) for site entry point
        road_width: Road width in meters
        max_grade: Maximum grade percentage
        min_curve_radius: Minimum turning radius in meters (for future use)
        grid_resolution: Pathfinding grid resolution in meters
        optimization_criteria: Optimization strategy
        exclusion_buffer: Buffer distance from exclusion zones in meters
        dem_path: Optional path to DEM raster for elevation data
        exclusion_zones: Optional list of exclusion zone geometries (GeoJSON)
        advanced_settings: Optional advanced configuration
        progress_callback: Optional callback for progress updates

    Returns:
        RoadNetworkResult object
    """
    start_time = time.time()
    progress = ProgressTracker(callback=progress_callback)
    algorithm_iterations = 0

    try:
        if len(asset_positions) < 1:
            return RoadNetworkResult(
                success=False, error_message="No assets to connect"
            )

        # Step 1: Calculate bounds and generate grid
        progress.update(1, "Generating pathfinding grid")

        all_points = list(asset_positions)
        if entry_point:
            all_points.append(entry_point)

        lons = [p[0] for p in all_points]
        lats = [p[1] for p in all_points]

        # Add padding around bounds (10% or minimum 100m)
        padding = max(0.001, (max(lons) - min(lons)) * 0.1)
        bounds = (
            min(lons) - padding,
            min(lats) - padding,
            max(lons) + padding,
            max(lats) + padding,
        )

        nodes, num_rows, num_cols = generate_pathfinding_grid(bounds, grid_resolution)
        logger.info(f"Generated {len(nodes)} grid nodes ({num_rows}x{num_cols})")

        # Step 2: Load elevation data
        progress.update(2, "Loading elevation data")
        load_elevation_data(nodes, dem_path)

        # Step 3: Mark exclusion zones
        progress.update(3, "Processing exclusion zones")
        mark_exclusion_zones(nodes, exclusion_zones or [], exclusion_buffer)

        # Step 4: Build graph
        progress.update(4, "Building pathfinding graph")
        G = build_graph(nodes, num_rows, num_cols, max_grade, optimization_criteria)
        logger.info(
            f"Built graph with {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )

        if G.number_of_nodes() == 0:
            return RoadNetworkResult(
                success=False,
                error_message="No valid path nodes (check exclusions/terrain)",
            )

        # Step 5: Find paths between assets using MST
        progress.update(5, "Computing road paths")

        # Build MST to determine which assets to connect
        mst_edges = build_minimum_spanning_tree(asset_positions, G, nodes, num_cols)

        # If there's an entry point, connect it to the nearest asset
        if entry_point and asset_positions:
            # Find nearest asset to entry point
            min_dist = float("inf")
            nearest_asset = 0
            for i, (lon, lat) in enumerate(asset_positions):
                dist = haversine_distance(entry_point[0], entry_point[1], lon, lat)
                if dist < min_dist:
                    min_dist = dist
                    nearest_asset = i

            # Add entry point to the positions list and add edge
            entry_idx = len(asset_positions)
            all_positions = list(asset_positions) + [entry_point]
            mst_edges.append((entry_idx, nearest_asset))
        else:
            all_positions = list(asset_positions)

        # Find paths for all MST edges
        segments = []
        all_centerlines = []
        road_polygons = []
        segment_id = 0
        total_length = 0.0
        all_grades = []
        assets_connected_set = set()

        for asset_idx1, asset_idx2 in mst_edges:
            lon1, lat1 = all_positions[asset_idx1]
            lon2, lat2 = all_positions[asset_idx2]

            # Find nearest graph nodes
            node1 = find_nearest_node(G, nodes, num_cols, lon1, lat1)
            node2 = find_nearest_node(G, nodes, num_cols, lon2, lat2)

            if node1 is None or node2 is None:
                logger.warning(f"No graph nodes for assets {asset_idx1}, {asset_idx2}")
                continue

            # Find path using A*
            path = astar_path(G, node1, node2, nodes, num_cols)
            algorithm_iterations += 1

            if path is None:
                logger.warning(
                    f"No path found between assets {asset_idx1} and {asset_idx2}"
                )
                continue

            # Extract and simplify coordinates
            coords = extract_path_coordinates(path, G)
            coords = simplify_path(coords)

            # Calculate segment metrics
            length_m, avg_grade, max_grade_seg, cut_vol, fill_vol = (
                calculate_segment_metrics(coords)
            )

            # Create segment
            segment = RoadSegment(
                id=segment_id,
                from_node=asset_idx1,
                to_node=asset_idx2,
                coordinates=coords,
                length_m=length_m,
                avg_grade=avg_grade,
                max_grade=max_grade_seg,
                cut_volume=cut_vol,
                fill_volume=fill_vol,
            )
            segments.append(segment)

            # Track statistics
            total_length += length_m
            all_grades.append(avg_grade)
            if max_grade_seg > 0:
                all_grades.append(max_grade_seg)

            assets_connected_set.add(asset_idx1)
            assets_connected_set.add(asset_idx2)

            # Store centerline (2D for GeoJSON)
            centerline_2d = [[c[0], c[1]] for c in coords]
            all_centerlines.append(centerline_2d)

            # Create road polygon
            polygon = create_road_polygon(coords, road_width)
            if polygon:
                road_polygons.append(polygon)

            segment_id += 1

        # Step 6: Compile results
        progress.update(6, "Compiling results")

        # Merge road polygons
        combined_polygons = None
        if road_polygons:
            combined_polygons = unary_union(road_polygons)

        # Calculate statistics
        avg_grade_overall = float(np.mean(all_grades)) if all_grades else 0.0
        max_grade_overall = float(np.max(all_grades)) if all_grades else 0.0
        grade_compliant = max_grade_overall <= max_grade

        # Remove entry point from connected count if present
        num_assets_connected = len(
            [i for i in assets_connected_set if i < len(asset_positions)]
        )
        connectivity_rate = (
            (num_assets_connected / len(asset_positions) * 100)
            if asset_positions
            else 0.0
        )

        # Calculate earthwork totals
        total_cut = sum(s.cut_volume for s in segments)
        total_fill = sum(s.fill_volume for s in segments)

        # Build road details
        road_details = {
            "segments": [
                {
                    "id": s.id,
                    "from_node": s.from_node,
                    "to_node": s.to_node,
                    "length_m": s.length_m,
                    "avg_grade": s.avg_grade,
                    "max_grade": s.max_grade,
                    "cut_volume": s.cut_volume,
                    "fill_volume": s.fill_volume,
                    "coordinates": s.coordinates,
                }
                for s in segments
            ],
            "intersections": [],  # Could be computed if needed
        }

        processing_time = time.time() - start_time

        return RoadNetworkResult(
            success=True,
            road_centerlines=all_centerlines,
            road_polygons=combined_polygons,
            road_details=road_details,
            total_road_length=total_length,
            total_segments=len(segments),
            total_intersections=0,
            avg_grade=avg_grade_overall,
            max_grade_actual=max_grade_overall,
            grade_compliant=grade_compliant,
            total_cut_volume=total_cut,
            total_fill_volume=total_fill,
            net_earthwork_volume=total_cut - total_fill,
            assets_connected=num_assets_connected,
            connectivity_rate=connectivity_rate,
            processing_time=processing_time,
            memory_peak_mb=0.0,  # Placeholder
            algorithm_iterations=algorithm_iterations,
            pathfinding_algorithm="astar",
        )

    except Exception as e:
        logger.exception("Error during road network generation")
        err_msg = f"Road network generation failed: {str(e)}"
        return RoadNetworkResult(
            success=False,
            error_message=err_msg,
            processing_time=time.time() - start_time,
        )
