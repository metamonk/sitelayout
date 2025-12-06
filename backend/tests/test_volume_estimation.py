"""Tests for cut/fill volume estimation service."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from app.services.volume_estimation import (
    AssetVolumeResult,
    RoadSegmentVolumeResult,
    VolumeEstimationResult,
    calculate_asset_volume,
    calculate_road_segment_volume,
    create_asset_footprint,
    create_road_corridor,
    degrees_to_meters,
    estimate_volumes,
    generate_volumetric_report,
    get_foundation_dimensions,
    haversine_distance,
    meters_to_degrees,
)


class TestUnitConversions:
    """Tests for unit conversion functions."""

    def test_meters_to_degrees_at_equator(self):
        """Test meters to degrees conversion at equator."""
        # At equator, 1 degree ~ 111320 meters
        degrees = meters_to_degrees(111320, 0.0)
        assert degrees == pytest.approx(1.0, rel=0.01)

    def test_degrees_to_meters_at_equator(self):
        """Test degrees to meters conversion at equator."""
        meters = degrees_to_meters(1.0, 0.0)
        assert meters == pytest.approx(111320, rel=0.01)

    def test_conversion_round_trip(self):
        """Test that conversions are inverses."""
        original_meters = 1000.0
        latitude = 40.0
        degrees = meters_to_degrees(original_meters, latitude)
        back_to_meters = degrees_to_meters(degrees, latitude)
        assert back_to_meters == pytest.approx(original_meters, rel=0.01)

    def test_haversine_distance_same_point(self):
        """Distance between same point should be zero."""
        dist = haversine_distance(0.0, 0.0, 0.0, 0.0)
        assert dist == pytest.approx(0.0, abs=0.001)

    def test_haversine_distance_known_value(self):
        """Test haversine with known distance."""
        # London to Paris is approximately 343 km
        dist = haversine_distance(-0.1276, 51.5074, 2.3522, 48.8566)
        assert dist == pytest.approx(343800, rel=0.05)  # 5% tolerance


class TestFoundationDimensions:
    """Tests for foundation dimension lookup."""

    def test_pad_foundation(self):
        """Test pad foundation dimensions."""
        specs = get_foundation_dimensions("pad")
        assert specs["width"] == 20.0
        assert specs["length"] == 40.0
        assert specs["depth"] == 0.5

    def test_pier_foundation(self):
        """Test pier foundation dimensions."""
        specs = get_foundation_dimensions("pier")
        assert specs["depth"] == 1.5

    def test_unknown_foundation_defaults(self):
        """Unknown foundation type should return default."""
        specs = get_foundation_dimensions("unknown_type")
        assert specs["width"] == 20.0  # Default values

    def test_all_foundation_types(self):
        """Test all foundation types have required keys."""
        for ftype in ["pad", "pier", "strip", "raft"]:
            specs = get_foundation_dimensions(ftype)
            assert "width" in specs
            assert "length" in specs
            assert "depth" in specs


class TestAssetFootprint:
    """Tests for asset footprint creation."""

    def test_footprint_is_polygon(self):
        """Footprint should be a Shapely Polygon."""
        footprint = create_asset_footprint(0.0, 0.0, "pad")
        assert footprint.is_valid
        assert footprint.geom_type == "Polygon"

    def test_footprint_contains_center(self):
        """Footprint should contain its center point."""
        from shapely.geometry import Point

        lon, lat = 10.0, 45.0
        footprint = create_asset_footprint(lon, lat, "pad")
        center = Point(lon, lat)
        assert footprint.contains(center)

    def test_footprint_with_rotation(self):
        """Rotated footprint should still be valid."""
        footprint_0 = create_asset_footprint(0.0, 0.0, "pad", rotation=0)
        footprint_45 = create_asset_footprint(0.0, 0.0, "pad", rotation=45)
        footprint_90 = create_asset_footprint(0.0, 0.0, "pad", rotation=90)

        assert footprint_0.is_valid
        assert footprint_45.is_valid
        assert footprint_90.is_valid

        # Areas should be approximately equal
        assert footprint_0.area == pytest.approx(footprint_45.area, rel=0.01)
        assert footprint_0.area == pytest.approx(footprint_90.area, rel=0.01)


class TestRoadCorridor:
    """Tests for road corridor creation."""

    def test_corridor_is_polygon(self):
        """Road corridor should be a polygon."""
        coords = [[0.0, 0.0, 100.0], [0.01, 0.01, 100.0]]
        corridor = create_road_corridor(coords, road_width=6.0)
        assert corridor is not None
        assert corridor.is_valid
        assert corridor.geom_type == "Polygon"

    def test_corridor_too_few_points(self):
        """Corridor with < 2 points should return None."""
        coords = [[0.0, 0.0, 100.0]]
        corridor = create_road_corridor(coords, road_width=6.0)
        assert corridor is None

    def test_corridor_contains_centerline(self):
        """Corridor should contain its centerline."""
        from shapely.geometry import LineString

        coords = [[0.0, 0.0, 100.0], [0.01, 0.0, 100.0], [0.02, 0.0, 100.0]]
        corridor = create_road_corridor(coords, road_width=6.0)

        centerline = LineString([(c[0], c[1]) for c in coords])
        assert corridor.contains(centerline)


class TestAssetVolumeResult:
    """Tests for AssetVolumeResult dataclass."""

    def test_default_values(self):
        """Test default values of AssetVolumeResult."""
        result = AssetVolumeResult(
            asset_id=1,
            position=(0.0, 0.0),
            foundation_type="pad",
        )
        assert result.cut_volume_m3 == 0.0
        assert result.fill_volume_m3 == 0.0
        assert result.net_volume_m3 == 0.0

    def test_with_values(self):
        """Test AssetVolumeResult with values."""
        result = AssetVolumeResult(
            asset_id=1,
            position=(10.0, 45.0),
            foundation_type="pier",
            cut_volume_m3=1000.0,
            fill_volume_m3=500.0,
            net_volume_m3=500.0,
            footprint_area_m2=800.0,
        )
        assert result.cut_volume_m3 == 1000.0
        assert result.fill_volume_m3 == 500.0


class TestRoadSegmentVolumeResult:
    """Tests for RoadSegmentVolumeResult dataclass."""

    def test_default_values(self):
        """Test default values of RoadSegmentVolumeResult."""
        result = RoadSegmentVolumeResult(
            segment_id=1,
            from_asset=1,
            to_asset=2,
        )
        assert result.cut_volume_m3 == 0.0
        assert result.road_length_m == 0.0

    def test_with_values(self):
        """Test RoadSegmentVolumeResult with values."""
        result = RoadSegmentVolumeResult(
            segment_id=1,
            from_asset=1,
            to_asset=2,
            cut_volume_m3=500.0,
            fill_volume_m3=300.0,
            road_length_m=150.0,
        )
        assert result.cut_volume_m3 == 500.0
        assert result.road_length_m == 150.0


class TestVolumeEstimationResult:
    """Tests for VolumeEstimationResult dataclass."""

    def test_success_result(self):
        """Test successful VolumeEstimationResult."""
        result = VolumeEstimationResult(
            success=True,
            total_cut_volume_m3=5000.0,
            total_fill_volume_m3=4000.0,
            total_net_volume_m3=1000.0,
            cut_fill_ratio=1.25,
        )
        assert result.success
        assert result.total_cut_volume_m3 == 5000.0

    def test_failure_result(self):
        """Test failed VolumeEstimationResult."""
        result = VolumeEstimationResult(
            success=False,
            error_message="Test error",
        )
        assert not result.success
        assert result.error_message == "Test error"


class TestVolumetricReport:
    """Tests for volumetric report generation."""

    def test_report_structure(self):
        """Test that report has expected structure."""
        result = VolumeEstimationResult(
            success=True,
            asset_volumes=[
                AssetVolumeResult(
                    asset_id=1,
                    position=(0.0, 0.0),
                    foundation_type="pad",
                    cut_volume_m3=100.0,
                    fill_volume_m3=50.0,
                    net_volume_m3=50.0,
                )
            ],
            road_volumes=[
                RoadSegmentVolumeResult(
                    segment_id=1,
                    from_asset=1,
                    to_asset=2,
                    cut_volume_m3=200.0,
                    fill_volume_m3=100.0,
                )
            ],
            total_asset_cut_volume_m3=100.0,
            total_asset_fill_volume_m3=50.0,
            total_road_cut_volume_m3=200.0,
            total_road_fill_volume_m3=100.0,
            total_cut_volume_m3=300.0,
            total_fill_volume_m3=150.0,
            total_net_volume_m3=150.0,
            cut_fill_ratio=2.0,
        )

        report = generate_volumetric_report(result, "Test Project")

        assert report["project_name"] == "Test Project"
        assert "summary" in report
        assert "asset_breakdown" in report
        assert "road_breakdown" in report
        assert "processing_metadata" in report

    def test_report_summary_values(self):
        """Test report summary contains correct values."""
        result = VolumeEstimationResult(
            success=True,
            total_cut_volume_m3=1000.0,
            total_fill_volume_m3=800.0,
            total_net_volume_m3=200.0,
            cut_fill_ratio=1.25,
        )

        report = generate_volumetric_report(result)

        assert report["summary"]["total_cut_volume_m3"] == 1000.0
        assert report["summary"]["total_fill_volume_m3"] == 800.0
        assert report["summary"]["balance_status"] == "Excess Cut"

    def test_report_balanced_status(self):
        """Test balanced cut/fill status."""
        result = VolumeEstimationResult(
            success=True,
            total_cut_volume_m3=1000.0,
            total_fill_volume_m3=1000.0,
            total_net_volume_m3=0.0,
            cut_fill_ratio=1.0,
        )

        report = generate_volumetric_report(result)
        assert report["summary"]["balance_status"] == "Balanced"

    def test_report_excess_fill_status(self):
        """Test excess fill status."""
        result = VolumeEstimationResult(
            success=True,
            total_cut_volume_m3=500.0,
            total_fill_volume_m3=1000.0,
            total_net_volume_m3=-500.0,
            cut_fill_ratio=0.5,
        )

        report = generate_volumetric_report(result)
        assert report["summary"]["balance_status"] == "Excess Fill"

    def test_report_failure(self):
        """Test report for failed estimation."""
        result = VolumeEstimationResult(
            success=False,
            error_message="DEM file not found",
        )

        report = generate_volumetric_report(result)
        assert not report["success"]
        assert report["error"] == "DEM file not found"


class TestEstimateVolumesWithMock:
    """Tests for volume estimation with mocked DEM data."""

    def create_test_dem(self, tmpdir, elevation_func=None):
        """Create a test DEM file."""

        # Create a simple 100x100 DEM
        def default_elevation(x, y):
            return 100.0 + x * 0.5 + y * 0.5

        if elevation_func is None:
            elevation_func = default_elevation

        dem_path = os.path.join(tmpdir, "test_dem.tif")
        width, height = 100, 100

        # Create elevation data
        x = np.arange(width)
        y = np.arange(height)
        xx, yy = np.meshgrid(x, y)
        elevation = elevation_func(xx, yy).astype(np.float32)

        # Write DEM
        transform = from_bounds(-0.01, -0.01, 0.01, 0.01, width, height)
        with rasterio.open(
            dem_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=elevation.dtype,
            crs=CRS.from_epsg(4326),
            transform=transform,
        ) as dst:
            dst.write(elevation, 1)

        return dem_path

    def test_estimate_volumes_no_input(self):
        """Test estimation with no assets or roads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = self.create_test_dem(tmpdir)

            result = estimate_volumes(
                asset_positions=[],
                road_segments=None,
                dem_path=dem_path,
                grid_resolution=2.0,
            )

            assert not result.success
            assert "No assets or roads provided" in result.error_message

    def test_estimate_volumes_with_assets(self):
        """Test estimation with assets only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = self.create_test_dem(tmpdir)

            asset_positions = [
                {"id": 1, "position": [0.0, 0.0]},
                {"id": 2, "position": [0.005, 0.005]},
            ]

            result = estimate_volumes(
                asset_positions=asset_positions,
                road_segments=None,
                dem_path=dem_path,
                grid_resolution=2.0,
            )

            assert result.success
            assert len(result.asset_volumes) == 2
            assert result.total_cells_analyzed > 0

    def test_estimate_volumes_with_roads(self):
        """Test estimation with road segments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = self.create_test_dem(tmpdir)

            asset_positions = [
                {"id": 1, "position": [0.0, 0.0]},
            ]

            road_segments = [
                {
                    "id": 1,
                    "from_node": 1,
                    "to_node": 2,
                    "coordinates": [
                        [0.0, 0.0, 100.0],
                        [0.005, 0.0, 105.0],
                        [0.005, 0.005, 110.0],
                    ],
                }
            ]

            result = estimate_volumes(
                asset_positions=asset_positions,
                road_segments=road_segments,
                dem_path=dem_path,
                grid_resolution=2.0,
            )

            assert result.success
            assert len(result.road_volumes) == 1

    def test_estimate_volumes_grid_resolution_clamping(self):
        """Test that grid resolution is clamped to valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = self.create_test_dem(tmpdir)

            asset_positions = [{"id": 1, "position": [0.0, 0.0]}]

            # Test with resolution too small
            result = estimate_volumes(
                asset_positions=asset_positions,
                road_segments=None,
                dem_path=dem_path,
                grid_resolution=0.1,  # Should be clamped to 1
            )

            assert result.success
            assert result.grid_cell_size >= 1.0

    def test_estimate_volumes_invalid_dem(self):
        """Test estimation with invalid DEM path."""
        result = estimate_volumes(
            asset_positions=[{"id": 1, "position": [0.0, 0.0]}],
            road_segments=None,
            dem_path="/nonexistent/path.tif",
            grid_resolution=2.0,
        )

        assert not result.success
        assert "Failed to read DEM file" in result.error_message

    def test_estimate_volumes_includes_visualization(self):
        """Test that visualization data is generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = self.create_test_dem(tmpdir)

            asset_positions = [{"id": 1, "position": [0.0, 0.0]}]

            result = estimate_volumes(
                asset_positions=asset_positions,
                road_segments=None,
                dem_path=dem_path,
                grid_resolution=2.0,
                include_visualization=True,
            )

            assert result.success
            assert result.visualization_data is not None
            assert "bounds" in result.visualization_data
            assert "assets" in result.visualization_data

    def test_estimate_volumes_no_visualization(self):
        """Test that visualization can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dem_path = self.create_test_dem(tmpdir)

            asset_positions = [{"id": 1, "position": [0.0, 0.0]}]

            result = estimate_volumes(
                asset_positions=asset_positions,
                road_segments=None,
                dem_path=dem_path,
                grid_resolution=2.0,
                include_visualization=False,
            )

            assert result.success
            assert result.visualization_data is None


class TestVolumeCalculationsWithMock:
    """Tests for volume calculations with mocked rasterio."""

    @patch("app.services.volume_estimation.rasterio.open")
    def test_calculate_asset_volume_flat_terrain(self, mock_open):
        """Test asset volume on flat terrain."""
        mock_dataset = MagicMock()
        mock_dataset.nodata = -9999

        # Return constant elevation for all samples
        def mock_sample(points):
            for _ in points:
                yield [100.0]

        mock_dataset.sample = mock_sample
        mock_open.return_value.__enter__.return_value = mock_dataset

        result = calculate_asset_volume(
            lon=0.0,
            lat=0.0,
            foundation_type="pad",
            dem_path="/fake/dem.tif",
            grid_resolution=2.0,
        )

        # On flat terrain at design elevation, volumes should be minimal
        # (just foundation depth excavation)
        assert result.cut_volume_m3 >= 0.0
        assert result.foundation_type == "pad"

    @patch("app.services.volume_estimation.rasterio.open")
    def test_calculate_road_segment_volume_flat(self, mock_open):
        """Test road segment volume on flat terrain."""
        mock_dataset = MagicMock()
        mock_dataset.nodata = -9999

        def mock_sample(points):
            for _ in points:
                yield [100.0]

        mock_dataset.sample = mock_sample
        mock_open.return_value.__enter__.return_value = mock_dataset

        coordinates = [
            [0.0, 0.0, 100.0],
            [0.001, 0.0, 100.0],
            [0.002, 0.0, 100.0],
        ]

        result = calculate_road_segment_volume(
            coordinates=coordinates,
            road_width=6.0,
            dem_path="/fake/dem.tif",
            grid_resolution=2.0,
        )

        # On flat terrain with matching design elevations, volumes should be minimal
        assert result.cut_volume_m3 >= 0.0
        assert result.road_length_m > 0.0

    @patch("app.services.volume_estimation.rasterio.open")
    def test_calculate_asset_volume_with_cut(self, mock_open):
        """Test asset volume where cut is needed."""
        mock_dataset = MagicMock()
        mock_dataset.nodata = -9999

        # Return higher elevation than design - requires cutting
        def mock_sample(points):
            for _ in points:
                yield [120.0]  # Higher than what we'd design for

        mock_dataset.sample = mock_sample
        mock_open.return_value.__enter__.return_value = mock_dataset

        result = calculate_asset_volume(
            lon=0.0,
            lat=0.0,
            foundation_type="pad",
            dem_path="/fake/dem.tif",
            grid_resolution=2.0,
            design_elevation=100.0,  # Lower than terrain
        )

        # Should have cut volume
        assert result.cut_volume_m3 > 0.0

    @patch("app.services.volume_estimation.rasterio.open")
    def test_calculate_asset_volume_with_fill(self, mock_open):
        """Test asset volume where fill is needed."""
        mock_dataset = MagicMock()
        mock_dataset.nodata = -9999

        # Return lower elevation than design - requires filling
        def mock_sample(points):
            for _ in points:
                yield [80.0]  # Lower than design

        mock_dataset.sample = mock_sample
        mock_open.return_value.__enter__.return_value = mock_dataset

        result = calculate_asset_volume(
            lon=0.0,
            lat=0.0,
            foundation_type="pad",
            dem_path="/fake/dem.tif",
            grid_resolution=2.0,
            design_elevation=100.0,  # Higher than terrain
        )

        # Should have fill volume
        assert result.fill_volume_m3 > 0.0


class TestProgressCallback:
    """Tests for progress callback functionality."""

    def test_estimate_volumes_with_progress(self):
        """Test that progress callback is called."""
        progress_calls = []

        def track_progress(percent, step):
            progress_calls.append((percent, step))

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test DEM
            dem_path = os.path.join(tmpdir, "test_dem.tif")
            elevation = np.full((50, 50), 100.0, dtype=np.float32)
            transform = from_bounds(-0.005, -0.005, 0.005, 0.005, 50, 50)

            with rasterio.open(
                dem_path,
                "w",
                driver="GTiff",
                height=50,
                width=50,
                count=1,
                dtype=elevation.dtype,
                crs=CRS.from_epsg(4326),
                transform=transform,
            ) as dst:
                dst.write(elevation, 1)

            result = estimate_volumes(
                asset_positions=[{"id": 1, "position": [0.0, 0.0]}],
                road_segments=None,
                dem_path=dem_path,
                grid_resolution=2.0,
                progress_callback=track_progress,
            )

            assert result.success
            assert len(progress_calls) > 0
            # Check progress increases
            percents = [p[0] for p in progress_calls]
            assert percents == sorted(percents)  # Should be monotonically increasing
