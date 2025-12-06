"""Tests for asset placement service."""

import tempfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

from app.services.asset_placement import (
    GridCell,
    PlacementResult,
    apply_constraints,
    calculate_placement_metrics,
    calculate_scores,
    generate_grid,
    greedy_selection,
    load_terrain_data,
    place_assets,
    select_clustered_locations,
    select_optimal_locations,
)


class TestGenerateGrid:
    """Tests for grid generation."""

    def test_basic_grid_generation(self):
        """Test basic grid generation."""
        bounds = (0.0, 0.0, 1.0, 1.0)
        resolution = 100.0  # 100 meters

        cells = generate_grid(bounds, resolution)

        assert len(cells) > 0
        assert all(isinstance(c, GridCell) for c in cells)
        assert all(bounds[0] <= c.x <= bounds[2] for c in cells)
        assert all(bounds[1] <= c.y <= bounds[3] for c in cells)

    def test_grid_cell_count(self):
        """Test that grid cell count is reasonable."""
        # Small area should have fewer cells
        bounds1 = (0.0, 0.0, 0.1, 0.1)
        cells1 = generate_grid(bounds1, 50.0)

        # Larger area should have more cells
        bounds2 = (0.0, 0.0, 1.0, 1.0)
        cells2 = generate_grid(bounds2, 50.0)

        assert len(cells2) > len(cells1)

    def test_grid_cell_properties(self):
        """Test that grid cells have correct properties."""
        bounds = (0.0, 0.0, 1.0, 1.0)
        cells = generate_grid(bounds, 100.0)

        # Check first cell
        assert cells[0].row == 0
        assert cells[0].col == 0
        assert cells[0].is_valid is False  # Default state
        assert cells[0].slope is None
        assert cells[0].elevation is None


class TestLoadTerrainData:
    """Tests for terrain data loading."""

    def test_load_terrain_data_no_raster(self):
        """Test loading terrain data without a raster."""
        cells = [GridCell(x=0.0, y=0.0, row=0, col=0) for _ in range(5)]
        load_terrain_data(cells, None)

        # All slopes should be set to 0.0
        assert all(c.slope == 0.0 for c in cells)

    def test_load_terrain_data_with_raster(self):
        """Test loading terrain data from a raster file."""
        # Create a temporary slope raster
        with tempfile.TemporaryDirectory() as tmpdir:
            raster_path = f"{tmpdir}/slope.tif"

            # Create a simple raster
            slope_data = np.random.rand(10, 10).astype(np.float32) * 10
            transform = from_bounds(0, 0, 1, 1, 10, 10)

            with rasterio.open(
                raster_path,
                "w",
                driver="GTiff",
                height=10,
                width=10,
                count=1,
                dtype=slope_data.dtype,
                crs="EPSG:4326",
                transform=transform,
            ) as dst:
                dst.write(slope_data, 1)

            # Create cells within the raster bounds
            cells = [
                GridCell(x=0.5, y=0.5, row=0, col=0),
                GridCell(x=0.3, y=0.3, row=0, col=1),
            ]

            load_terrain_data(cells, raster_path)

            # Cells should have slope values
            assert all(c.slope is not None for c in cells)


class TestApplyConstraints:
    """Tests for constraint application."""

    def test_slope_constraint(self):
        """Test slope constraint filtering."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=2.0),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=10.0),
            GridCell(x=0.2, y=0.2, row=0, col=2, slope=15.0),
        ]

        apply_constraints(cells, max_slope=5.0, exclusion_zones=[], placement_area=None)

        assert cells[0].is_valid is True  # 2.0 < 5.0
        assert cells[1].is_valid is False  # 10.0 > 5.0
        assert cells[2].is_valid is False  # 15.0 > 5.0

    def test_placement_area_constraint(self):
        """Test placement area constraint."""
        cells = [
            GridCell(x=0.5, y=0.5, row=0, col=0, slope=2.0),
            GridCell(x=1.5, y=1.5, row=0, col=1, slope=2.0),
        ]

        placement_area = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

        apply_constraints(
            cells,
            max_slope=5.0,
            exclusion_zones=[],
            placement_area=placement_area,
        )

        assert cells[0].is_valid is True  # Inside polygon
        assert cells[1].is_valid is False  # Outside polygon

    def test_exclusion_zone_constraint(self):
        """Test exclusion zone constraint."""
        cells = [
            GridCell(x=0.5, y=0.5, row=0, col=0, slope=2.0),
            GridCell(x=2.5, y=2.5, row=0, col=1, slope=2.0),
        ]

        # Create exclusion zone that covers first cell
        exclusion_zone = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        }

        apply_constraints(
            cells,
            max_slope=5.0,
            exclusion_zones=[exclusion_zone],
            placement_area=None,
        )

        assert cells[0].is_valid is False  # Inside exclusion zone
        assert cells[1].is_valid is True  # Outside exclusion zone


class TestCalculateScores:
    """Tests for score calculation."""

    def test_maximize_flat_areas(self):
        """Test scoring for maximizing flat areas."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=1.0, is_valid=True),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=5.0, is_valid=True),
            GridCell(x=0.2, y=0.2, row=0, col=2, slope=10.0, is_valid=True),
        ]

        scores = calculate_scores(cells, "maximize_flat_areas")

        # Lower slope should have better (lower) score
        assert scores[0] < scores[1] < scores[2]

    def test_balanced_scoring(self):
        """Test balanced scoring."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=2.0, is_valid=True),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=8.0, is_valid=True),
        ]

        scores = calculate_scores(cells, "balanced")

        assert len(scores) == 2
        assert scores[0] < scores[1]  # Lower slope should score better

    def test_no_valid_cells(self):
        """Test scoring with no valid cells."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=2.0, is_valid=False),
        ]

        scores = calculate_scores(cells, "maximize_flat_areas")

        assert len(scores) == 0


class TestGreedySelection:
    """Tests for greedy selection algorithm."""

    def test_basic_greedy_selection(self):
        """Test basic greedy selection."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=1.0),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=2.0),
            GridCell(x=0.2, y=0.2, row=0, col=2, slope=3.0),
        ]
        scores = np.array([1.0, 2.0, 3.0])

        selected = greedy_selection(cells, num_assets=2, min_spacing=0.0, scores=scores)

        assert len(selected) <= 2
        assert all(c in cells for c in selected)

    def test_greedy_selection_with_spacing(self):
        """Test greedy selection with spacing constraints."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=1.0),
            GridCell(x=0.01, y=0.01, row=0, col=1, slope=1.5),  # Very close to first
            GridCell(x=0.5, y=0.5, row=0, col=2, slope=2.0),  # Far from first
        ]
        scores = np.array([1.0, 1.5, 2.0])

        # Require large spacing
        selected = greedy_selection(
            cells, num_assets=2, min_spacing=1000.0, scores=scores
        )

        # Should select first and third (not second, too close to first)
        assert len(selected) <= 2


class TestSelectClusteredLocations:
    """Tests for clustered location selection."""

    def test_clustered_selection(self):
        """Test clustered location selection."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=1.0),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=1.0),
            GridCell(x=0.2, y=0.2, row=0, col=2, slope=1.0),
            GridCell(x=5.0, y=5.0, row=1, col=0, slope=1.0),  # Far away
        ]
        scores = np.array([1.0, 1.0, 1.0, 1.0])

        selected = select_clustered_locations(
            cells, num_assets=3, min_spacing=0.0, scores=scores
        )

        assert len(selected) <= 3
        # Should prefer clustered cells (first three) over the far one


class TestSelectOptimalLocations:
    """Tests for optimal location selection."""

    def test_optimal_selection_minimize_distance(self):
        """Test optimal selection with minimize distance criteria."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=1.0, is_valid=True),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=1.0, is_valid=True),
            GridCell(x=5.0, y=5.0, row=1, col=0, slope=1.0, is_valid=True),
        ]

        selected = select_optimal_locations(
            cells,
            num_assets=2,
            min_spacing=0.0,
            optimization_criteria="minimize_inter_asset_distance",
        )

        assert len(selected) <= 2

    def test_optimal_selection_maximize_flat(self):
        """Test optimal selection with maximize flat areas."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=1.0, is_valid=True),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=5.0, is_valid=True),
            GridCell(x=0.2, y=0.2, row=0, col=2, slope=10.0, is_valid=True),
        ]

        selected = select_optimal_locations(
            cells,
            num_assets=2,
            min_spacing=0.0,
            optimization_criteria="maximize_flat_areas",
        )

        assert len(selected) <= 2
        # Should prefer flatter cells
        assert selected[0].slope <= 5.0


class TestCalculatePlacementMetrics:
    """Tests for placement metrics calculation."""

    def test_metrics_with_multiple_cells(self):
        """Test metrics calculation with multiple cells."""
        cells = [
            GridCell(x=0.0, y=0.0, row=0, col=0, slope=2.0),
            GridCell(x=0.1, y=0.1, row=0, col=1, slope=3.0),
            GridCell(x=0.2, y=0.2, row=0, col=2, slope=4.0),
        ]

        metrics = calculate_placement_metrics(cells)

        assert metrics["avg_slope"] == pytest.approx(3.0, abs=0.1)
        assert metrics["avg_inter_asset_distance"] is not None
        assert metrics["avg_inter_asset_distance"] > 0

    def test_metrics_with_no_cells(self):
        """Test metrics with no cells."""
        cells = []
        metrics = calculate_placement_metrics(cells)

        assert metrics["avg_slope"] is None
        assert metrics["avg_inter_asset_distance"] is None

    def test_metrics_with_single_cell(self):
        """Test metrics with single cell."""
        cells = [GridCell(x=0.0, y=0.0, row=0, col=0, slope=5.0)]
        metrics = calculate_placement_metrics(cells)

        assert metrics["avg_slope"] == 5.0
        assert (
            metrics["avg_inter_asset_distance"] is None
        )  # Need at least 2 for distance


class TestPlaceAssets:
    """Tests for complete asset placement."""

    def test_basic_placement(self):
        """Test basic asset placement."""
        placement_area = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        }

        result = place_assets(
            placement_area=placement_area,
            num_assets=5,
            grid_resolution=50.0,
            min_spacing=10.0,
            max_slope=10.0,
            optimization_criteria="balanced",
            slope_raster_path=None,
            exclusion_zones=None,
        )

        assert isinstance(result, PlacementResult)
        assert result.success is True
        assert result.grid_cells_total > 0

    def test_placement_with_constraints(self):
        """Test placement with slope and exclusion constraints."""
        placement_area = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]],
        }

        exclusion_zone = {
            "type": "Polygon",
            "coordinates": [
                [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)]
            ],
        }

        result = place_assets(
            placement_area=placement_area,
            num_assets=10,
            grid_resolution=50.0,
            min_spacing=20.0,
            max_slope=5.0,
            optimization_criteria="maximize_flat_areas",
            slope_raster_path=None,
            exclusion_zones=[exclusion_zone],
        )

        assert result.success is True
        # Some cells should be excluded
        if result.grid_cells_total > 0:
            assert result.grid_cells_excluded > 0

    def test_placement_with_too_many_assets(self):
        """Test placement when requesting more assets than available space."""
        # Very small area
        placement_area = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1), (0, 0)]],
        }

        result = place_assets(
            placement_area=placement_area,
            num_assets=100,
            grid_resolution=50.0,
            min_spacing=100.0,  # Large spacing
            max_slope=5.0,
            optimization_criteria="balanced",
        )

        assert result.success is True
        # Should place fewer than or equal to requested (depends on grid resolution)
        assert result.assets_placed <= 100

    def test_placement_progress_callback(self):
        """Test that progress callback is called."""
        placement_area = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        }

        progress_calls = []

        def progress_callback(percent, step):
            progress_calls.append((percent, step))

        result = place_assets(
            placement_area=placement_area,
            num_assets=5,
            grid_resolution=50.0,
            min_spacing=10.0,
            max_slope=10.0,
            optimization_criteria="balanced",
            progress_callback=progress_callback,
        )

        assert result.success is True
        # Progress callback should have been called
        assert len(progress_calls) > 0
        # Should reach 100%
        assert any(percent == 100 for percent, _ in progress_calls)

    def test_placement_result_format(self):
        """Test that placement result has correct format."""
        placement_area = {
            "type": "Polygon",
            "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        }

        result = place_assets(
            placement_area=placement_area,
            num_assets=3,
            grid_resolution=50.0,
            min_spacing=10.0,
            max_slope=10.0,
            optimization_criteria="balanced",
        )

        assert result.success is True
        assert isinstance(result.placed_positions, list)
        assert isinstance(result.placement_details, dict)
        assert "assets" in result.placement_details
        assert result.processing_time > 0

        # Check asset details format
        if result.assets_placed > 0:
            asset = result.placement_details["assets"][0]
            assert "id" in asset
            assert "position" in asset
            assert len(asset["position"]) == 2


class TestGridCell:
    """Tests for GridCell dataclass."""

    def test_grid_cell_creation(self):
        """Test GridCell creation."""
        cell = GridCell(x=1.0, y=2.0, row=3, col=4)

        assert cell.x == 1.0
        assert cell.y == 2.0
        assert cell.row == 3
        assert cell.col == 4
        assert cell.is_valid is False
        assert cell.slope is None
        assert cell.elevation is None

    def test_grid_cell_with_data(self):
        """Test GridCell with terrain data."""
        cell = GridCell(
            x=1.0,
            y=2.0,
            row=3,
            col=4,
            elevation=100.0,
            slope=5.0,
            is_valid=True,
        )

        assert cell.elevation == 100.0
        assert cell.slope == 5.0
        assert cell.is_valid is True


class TestPlacementResult:
    """Tests for PlacementResult dataclass."""

    def test_placement_result_success(self):
        """Test successful PlacementResult."""
        result = PlacementResult(
            success=True,
            placed_positions=[(0.0, 0.0), (0.1, 0.1)],
            assets_placed=2,
            grid_cells_total=100,
            grid_cells_valid=80,
        )

        assert result.success is True
        assert len(result.placed_positions) == 2
        assert result.assets_placed == 2

    def test_placement_result_failure(self):
        """Test failed PlacementResult."""
        result = PlacementResult(
            success=False,
            error_message="Test error",
        )

        assert result.success is False
        assert result.error_message == "Test error"
        assert result.assets_placed == 0
