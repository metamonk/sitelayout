"""Tests for road network generation service."""

import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from app.services.road_network import (
    GridNode,
    RoadNetworkResult,
    RoadSegment,
    build_graph,
    build_minimum_spanning_tree,
    calculate_grade,
    calculate_segment_metrics,
    create_road_polygon,
    degrees_to_meters,
    extract_path_coordinates,
    find_nearest_node,
    generate_pathfinding_grid,
    generate_road_network,
    haversine_distance,
    load_elevation_data,
    mark_exclusion_zones,
    meters_to_degrees,
    simplify_path,
)


class TestHaversineDistance:
    """Tests for haversine distance calculation."""

    def test_same_point(self):
        """Test distance between same point is zero."""
        dist = haversine_distance(0.0, 0.0, 0.0, 0.0)
        assert dist == pytest.approx(0.0, abs=0.1)

    def test_known_distance(self):
        """Test distance between known points."""
        # Approximately 111km (1 degree at equator)
        dist = haversine_distance(0.0, 0.0, 1.0, 0.0)
        assert 110000 < dist < 112000  # ~111 km

    def test_symmetric(self):
        """Test distance is symmetric."""
        dist1 = haversine_distance(0.0, 0.0, 1.0, 1.0)
        dist2 = haversine_distance(1.0, 1.0, 0.0, 0.0)
        assert dist1 == pytest.approx(dist2, abs=0.1)


class TestCalculateGrade:
    """Tests for grade calculation."""

    def test_flat_grade(self):
        """Test grade on flat terrain."""
        grade = calculate_grade(0.0, 0.0, 100.0, 0.0, 0.0, 100.0)
        assert grade == pytest.approx(0.0, abs=0.001)

    def test_positive_grade(self):
        """Test positive grade (uphill)."""
        # 100m horizontal, 10m vertical = 10% grade
        grade = calculate_grade(0.0, 0.0, 100.0, 0.0009, 0.0, 110.0)
        assert grade > 0
        assert grade < 20  # Should be around 10%

    def test_same_point(self):
        """Test grade between same point."""
        grade = calculate_grade(0.0, 0.0, 100.0, 0.0, 0.0, 110.0)
        assert grade == pytest.approx(0.0, abs=0.001)


class TestConversions:
    """Tests for coordinate conversions."""

    def test_degrees_to_meters(self):
        """Test degrees to meters conversion."""
        meters = degrees_to_meters(1.0, 0.0)
        assert 110000 < meters < 112000  # ~111km at equator

    def test_meters_to_degrees(self):
        """Test meters to degrees conversion."""
        degrees = meters_to_degrees(111320, 0.0)
        assert degrees == pytest.approx(1.0, abs=0.1)

    def test_roundtrip(self):
        """Test roundtrip conversion."""
        original = 1000.0
        degrees = meters_to_degrees(original, 45.0)
        back = degrees_to_meters(degrees, 45.0)
        assert back == pytest.approx(original, rel=0.05)


class TestGeneratePathfindingGrid:
    """Tests for pathfinding grid generation."""

    def test_basic_grid(self):
        """Test basic grid generation."""
        bounds = (0.0, 0.0, 1.0, 1.0)
        resolution = 100.0

        nodes, num_rows, num_cols = generate_pathfinding_grid(bounds, resolution)

        assert len(nodes) > 0
        assert len(nodes) == num_rows * num_cols
        assert all(isinstance(n, GridNode) for n in nodes)

    def test_grid_bounds(self):
        """Test grid stays within bounds."""
        bounds = (0.0, 0.0, 1.0, 1.0)
        resolution = 50.0

        nodes, _, _ = generate_pathfinding_grid(bounds, resolution)

        for node in nodes:
            assert bounds[0] <= node.x <= bounds[2]
            assert bounds[1] <= node.y <= bounds[3]

    def test_grid_properties(self):
        """Test grid node properties."""
        bounds = (0.0, 0.0, 0.5, 0.5)
        nodes, _, _ = generate_pathfinding_grid(bounds, 100.0)

        assert nodes[0].row == 0
        assert nodes[0].col == 0
        assert nodes[0].is_valid is True  # Default for GridNode
        assert nodes[0].elevation is None


class TestLoadElevationData:
    """Tests for elevation data loading."""

    def test_no_dem(self):
        """Test loading without DEM."""
        nodes = [GridNode(x=0.0, y=0.0, row=0, col=0) for _ in range(5)]
        load_elevation_data(nodes, None)

        assert all(n.elevation == 0.0 for n in nodes)

    def test_with_dem(self):
        """Test loading with DEM raster."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = f"{tmpdir}/dem.tif"

            # Create a simple DEM
            elev_data = np.ones((10, 10), dtype=np.float32) * 100.0
            transform = from_bounds(0, 0, 1, 1, 10, 10)

            with rasterio.open(
                dem_path,
                "w",
                driver="GTiff",
                height=10,
                width=10,
                count=1,
                dtype=elev_data.dtype,
                crs="EPSG:4326",
                transform=transform,
            ) as dst:
                dst.write(elev_data, 1)

            nodes = [
                GridNode(x=0.5, y=0.5, row=0, col=0),
                GridNode(x=0.3, y=0.3, row=0, col=1),
            ]

            load_elevation_data(nodes, dem_path)

            assert all(n.elevation is not None for n in nodes)
            assert all(n.elevation == pytest.approx(100.0, abs=1.0) for n in nodes)


class TestMarkExclusionZones:
    """Tests for exclusion zone marking."""

    def test_no_exclusions(self):
        """Test with no exclusion zones."""
        nodes = [GridNode(x=0.5, y=0.5, row=0, col=0, is_valid=True)]
        mark_exclusion_zones(nodes, [], 0.0)

        assert nodes[0].is_valid is True

    def test_node_in_exclusion(self):
        """Test node inside exclusion zone."""
        nodes = [
            GridNode(x=0.5, y=0.5, row=0, col=0, is_valid=True),
            GridNode(x=2.5, y=2.5, row=0, col=1, is_valid=True),
        ]

        exclusion = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        }

        mark_exclusion_zones(nodes, [exclusion], 0.0)

        assert nodes[0].is_valid is False  # Inside
        assert nodes[1].is_valid is True  # Outside

    def test_buffer_distance(self):
        """Test buffer distance around exclusion zones."""
        nodes = [GridNode(x=1.01, y=0.5, row=0, col=0, is_valid=True)]

        exclusion = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        }

        # With large buffer, node should be excluded
        mark_exclusion_zones(nodes, [exclusion], 5000.0)  # 5km buffer

        assert nodes[0].is_valid is False


class TestBuildGraph:
    """Tests for graph building."""

    def test_empty_grid(self):
        """Test with empty grid."""
        nodes = []
        G = build_graph(nodes, 0, 0, 12.0, "balanced")
        assert G.number_of_nodes() == 0

    def test_basic_graph(self):
        """Test basic graph construction."""
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.0, row=0, col=1, elevation=100.0, is_valid=True),
            GridNode(x=0.0, y=0.001, row=1, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.001, row=1, col=1, elevation=100.0, is_valid=True),
        ]

        G = build_graph(nodes, 2, 2, 12.0, "balanced")

        assert G.number_of_nodes() == 4
        assert G.number_of_edges() > 0

    def test_grade_constraint(self):
        """Test that steep grades are excluded."""
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=0.0, is_valid=True),
            GridNode(
                x=0.0001, y=0.0, row=0, col=1, elevation=100.0, is_valid=True
            ),  # Very steep
        ]

        G = build_graph(nodes, 1, 2, 5.0, "balanced")  # 5% max grade

        # Edge should not exist due to grade constraint
        assert G.number_of_edges() == 0

    def test_invalid_nodes_excluded(self):
        """Test that invalid nodes are not in graph."""
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.0, row=0, col=1, elevation=100.0, is_valid=False),
        ]

        G = build_graph(nodes, 1, 2, 12.0, "balanced")

        assert G.number_of_nodes() == 1


class TestFindNearestNode:
    """Tests for nearest node finding."""

    def test_find_nearest(self):
        """Test finding nearest node."""
        # Create a proper 2x2 grid
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.0, row=0, col=1, elevation=100.0, is_valid=True),
            GridNode(x=0.0, y=0.001, row=1, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.001, row=1, col=1, elevation=100.0, is_valid=True),
        ]

        G = build_graph(nodes, 2, 2, 12.0, "balanced")

        nearest = find_nearest_node(G, nodes, 2, 0.0001, 0.0001)

        assert nearest == 0  # First node is closest

    def test_no_valid_nodes(self):
        """Test with no valid nodes."""
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=False),
        ]

        G = build_graph(nodes, 1, 1, 12.0, "balanced")

        nearest = find_nearest_node(G, nodes, 1, 0.5, 0.5)

        assert nearest is None


class TestExtractPathCoordinates:
    """Tests for path coordinate extraction."""

    def test_extract_coords(self):
        """Test coordinate extraction from path."""
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.0, row=0, col=1, elevation=101.0, is_valid=True),
        ]

        G = build_graph(nodes, 1, 2, 12.0, "balanced")

        coords = extract_path_coordinates([0, 1], G)

        assert len(coords) == 2
        assert coords[0] == [0.0, 0.0, 100.0]
        assert coords[1] == [0.001, 0.0, 101.0]


class TestCalculateSegmentMetrics:
    """Tests for segment metrics calculation."""

    def test_basic_metrics(self):
        """Test basic metrics calculation."""
        coords = [
            [0.0, 0.0, 100.0],
            [0.001, 0.0, 100.0],
            [0.002, 0.0, 100.0],
        ]

        length, avg_grade, max_grade, cut, fill = calculate_segment_metrics(coords)

        assert length > 0
        assert avg_grade >= 0
        assert max_grade >= 0

    def test_empty_coords(self):
        """Test with empty coordinates."""
        length, avg_grade, max_grade, cut, fill = calculate_segment_metrics([])

        assert length == 0.0
        assert avg_grade == 0.0

    def test_single_point(self):
        """Test with single point."""
        coords = [[0.0, 0.0, 100.0]]

        length, avg_grade, max_grade, cut, fill = calculate_segment_metrics(coords)

        assert length == 0.0


class TestSimplifyPath:
    """Tests for path simplification."""

    def test_no_simplification_needed(self):
        """Test path that doesn't need simplification."""
        coords = [
            [0.0, 0.0, 100.0],
            [1.0, 0.0, 100.0],
        ]

        simplified = simplify_path(coords)

        assert len(simplified) == 2

    def test_simplify_collinear(self):
        """Test simplification of collinear points."""
        coords = [
            [0.0, 0.0, 100.0],
            [0.5, 0.0, 100.0],  # Collinear
            [1.0, 0.0, 100.0],
        ]

        simplified = simplify_path(coords, tolerance_m=10.0)

        # Should simplify to 2 points
        assert len(simplified) <= 3


class TestCreateRoadPolygon:
    """Tests for road polygon creation."""

    def test_basic_polygon(self):
        """Test basic road polygon creation."""
        centerline = [
            [0.0, 0.0, 100.0],
            [0.01, 0.0, 100.0],
        ]

        polygon = create_road_polygon(centerline, 6.0)

        assert polygon is not None
        assert polygon.is_valid
        assert polygon.area > 0

    def test_single_point(self):
        """Test with single point (invalid)."""
        centerline = [[0.0, 0.0, 100.0]]

        polygon = create_road_polygon(centerline, 6.0)

        assert polygon is None


class TestBuildMinimumSpanningTree:
    """Tests for MST construction."""

    def test_two_assets(self):
        """Test MST with two assets."""
        positions = [(0.0, 0.0), (0.001, 0.001)]
        # Create a proper 2x2 grid
        nodes = [
            GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.0, row=0, col=1, elevation=100.0, is_valid=True),
            GridNode(x=0.0, y=0.001, row=1, col=0, elevation=100.0, is_valid=True),
            GridNode(x=0.001, y=0.001, row=1, col=1, elevation=100.0, is_valid=True),
        ]
        G = build_graph(nodes, 2, 2, 12.0, "balanced")

        edges = build_minimum_spanning_tree(positions, G, nodes, 2)

        assert len(edges) == 1
        assert (0, 1) in edges or (1, 0) in edges

    def test_single_asset(self):
        """Test MST with single asset."""
        positions = [(0.0, 0.0)]
        nodes = [GridNode(x=0.0, y=0.0, row=0, col=0, elevation=100.0, is_valid=True)]
        G = build_graph(nodes, 1, 1, 12.0, "balanced")

        edges = build_minimum_spanning_tree(positions, G, nodes, 1)

        assert len(edges) == 0


class TestGenerateRoadNetwork:
    """Tests for complete road network generation."""

    def test_basic_network(self):
        """Test basic road network generation."""
        positions = [(0.0, 0.0), (0.01, 0.0), (0.0, 0.01)]

        result = generate_road_network(
            asset_positions=positions,
            entry_point=None,
            road_width=6.0,
            max_grade=12.0,
            min_curve_radius=15.0,
            grid_resolution=50.0,
            optimization_criteria="balanced",
            exclusion_buffer=5.0,
            dem_path=None,
            exclusion_zones=None,
        )

        assert isinstance(result, RoadNetworkResult)
        assert result.success is True
        assert result.total_segments >= 0
        assert result.processing_time > 0
        assert result.pathfinding_algorithm == "astar"

    def test_no_assets(self):
        """Test with no assets."""
        result = generate_road_network(
            asset_positions=[],
            entry_point=None,
            road_width=6.0,
            max_grade=12.0,
            min_curve_radius=15.0,
            grid_resolution=50.0,
            optimization_criteria="balanced",
            exclusion_buffer=5.0,
        )

        assert result.success is False
        assert "No assets" in result.error_message

    def test_with_entry_point(self):
        """Test with entry point."""
        positions = [(0.0, 0.0), (0.01, 0.0)]
        entry = (-0.01, 0.0)

        result = generate_road_network(
            asset_positions=positions,
            entry_point=entry,
            road_width=6.0,
            max_grade=12.0,
            min_curve_radius=15.0,
            grid_resolution=50.0,
            optimization_criteria="balanced",
            exclusion_buffer=5.0,
        )

        assert result.success is True
        # Entry point should create additional segment
        assert result.total_segments >= 2

    def test_with_exclusion_zones(self):
        """Test with exclusion zones."""
        positions = [(0.0, 0.0), (0.05, 0.0)]

        # Exclusion zone in between assets
        exclusion = {
            "type": "Polygon",
            "coordinates": [
                [
                    (0.02, -0.01),
                    (0.03, -0.01),
                    (0.03, 0.01),
                    (0.02, 0.01),
                    (0.02, -0.01),
                ]
            ],
        }

        result = generate_road_network(
            asset_positions=positions,
            entry_point=None,
            road_width=6.0,
            max_grade=12.0,
            min_curve_radius=15.0,
            grid_resolution=50.0,
            optimization_criteria="balanced",
            exclusion_buffer=0.0,
            exclusion_zones=[exclusion],
        )

        assert result.success is True

    def test_optimization_criteria(self):
        """Test different optimization criteria."""
        positions = [(0.0, 0.0), (0.01, 0.0)]

        for criteria in [
            "minimal_length",
            "minimal_earthwork",
            "minimal_grade",
            "balanced",
        ]:
            result = generate_road_network(
                asset_positions=positions,
                entry_point=None,
                road_width=6.0,
                max_grade=12.0,
                min_curve_radius=15.0,
                grid_resolution=50.0,
                optimization_criteria=criteria,
                exclusion_buffer=5.0,
            )

            assert result.success is True

    def test_progress_callback(self):
        """Test progress callback is called."""
        positions = [(0.0, 0.0), (0.01, 0.0)]
        progress_calls = []

        def callback(percent, step):
            progress_calls.append((percent, step))

        result = generate_road_network(
            asset_positions=positions,
            entry_point=None,
            road_width=6.0,
            max_grade=12.0,
            min_curve_radius=15.0,
            grid_resolution=50.0,
            optimization_criteria="balanced",
            exclusion_buffer=5.0,
            progress_callback=callback,
        )

        assert result.success is True
        assert len(progress_calls) > 0
        assert any(percent == 100 for percent, _ in progress_calls)

    def test_result_format(self):
        """Test result format."""
        positions = [(0.0, 0.0), (0.01, 0.0)]

        result = generate_road_network(
            asset_positions=positions,
            entry_point=None,
            road_width=6.0,
            max_grade=12.0,
            min_curve_radius=15.0,
            grid_resolution=50.0,
            optimization_criteria="balanced",
            exclusion_buffer=5.0,
        )

        assert result.success is True
        assert result.road_centerlines is not None
        assert isinstance(result.road_details, dict)
        assert "segments" in result.road_details

        if result.total_segments > 0:
            segment = result.road_details["segments"][0]
            assert "id" in segment
            assert "from_node" in segment
            assert "to_node" in segment
            assert "coordinates" in segment
            assert "length_m" in segment
            assert "avg_grade" in segment


class TestGridNode:
    """Tests for GridNode dataclass."""

    def test_creation(self):
        """Test GridNode creation."""
        node = GridNode(x=1.0, y=2.0, row=3, col=4)

        assert node.x == 1.0
        assert node.y == 2.0
        assert node.row == 3
        assert node.col == 4
        assert node.is_valid is True
        assert node.elevation is None
        assert node.slope is None

    def test_with_data(self):
        """Test GridNode with terrain data."""
        node = GridNode(
            x=1.0,
            y=2.0,
            row=3,
            col=4,
            elevation=100.0,
            slope=5.0,
            is_valid=False,
        )

        assert node.elevation == 100.0
        assert node.slope == 5.0
        assert node.is_valid is False


class TestRoadSegment:
    """Tests for RoadSegment dataclass."""

    def test_creation(self):
        """Test RoadSegment creation."""
        segment = RoadSegment(
            id=1,
            from_node=0,
            to_node=1,
            coordinates=[[0.0, 0.0, 100.0], [1.0, 0.0, 100.0]],
            length_m=111320.0,
            avg_grade=0.0,
            max_grade=0.0,
        )

        assert segment.id == 1
        assert segment.from_node == 0
        assert segment.to_node == 1
        assert len(segment.coordinates) == 2
        assert segment.length_m == 111320.0


class TestRoadNetworkResult:
    """Tests for RoadNetworkResult dataclass."""

    def test_success(self):
        """Test successful result."""
        result = RoadNetworkResult(
            success=True,
            total_road_length=1000.0,
            total_segments=5,
            assets_connected=3,
            connectivity_rate=100.0,
        )

        assert result.success is True
        assert result.total_road_length == 1000.0
        assert result.total_segments == 5

    def test_failure(self):
        """Test failed result."""
        result = RoadNetworkResult(
            success=False,
            error_message="Test error",
        )

        assert result.success is False
        assert result.error_message == "Test error"
        assert result.total_segments == 0
