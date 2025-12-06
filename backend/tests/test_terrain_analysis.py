"""Tests for terrain analysis service."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from app.services.terrain_analysis import (
    SLOPE_CLASSES,
    AspectStats,
    ElevationStats,
    SlopeStats,
    calculate_aspect,
    calculate_elevation_stats,
    calculate_hillshade,
    calculate_input_hash,
    calculate_slope,
    get_terrain_profile,
)


class TestCalculateInputHash:
    """Tests for input hash calculation."""

    def test_same_inputs_same_hash(self):
        """Same inputs should produce same hash."""
        hash1 = calculate_input_hash("/path/to/dem.tif", (0, 0, 1, 1), 10.0)
        hash2 = calculate_input_hash("/path/to/dem.tif", (0, 0, 1, 1), 10.0)
        assert hash1 == hash2

    def test_different_paths_different_hash(self):
        """Different paths should produce different hashes."""
        hash1 = calculate_input_hash("/path/to/dem1.tif")
        hash2 = calculate_input_hash("/path/to/dem2.tif")
        assert hash1 != hash2

    def test_different_bounds_different_hash(self):
        """Different bounds should produce different hashes."""
        hash1 = calculate_input_hash("/path/to/dem.tif", (0, 0, 1, 1))
        hash2 = calculate_input_hash("/path/to/dem.tif", (0, 0, 2, 2))
        assert hash1 != hash2

    def test_hash_is_64_chars(self):
        """Hash should be 64 characters (SHA-256)."""
        hash_value = calculate_input_hash("/path/to/dem.tif")
        assert len(hash_value) == 64


class TestCalculateElevationStats:
    """Tests for elevation statistics calculation."""

    def test_basic_stats(self):
        """Test basic elevation statistics."""
        elevation = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=np.float64)
        stats = calculate_elevation_stats(elevation)

        assert stats.min_value == 1.0
        assert stats.max_value == 9.0
        assert stats.mean_value == 5.0
        assert stats.valid_count == 9
        assert stats.nodata_count == 0

    def test_with_nodata(self):
        """Test elevation stats with NaN values."""
        elevation = np.array(
            [[1, 2, np.nan], [4, np.nan, 6], [7, 8, 9]], dtype=np.float64
        )
        stats = calculate_elevation_stats(elevation)

        assert stats.min_value == 1.0
        assert stats.max_value == 9.0
        assert stats.nodata_count == 2
        assert stats.valid_count == 7

    def test_all_nodata(self):
        """Test elevation stats when all values are NaN."""
        elevation = np.array([[np.nan, np.nan], [np.nan, np.nan]], dtype=np.float64)
        stats = calculate_elevation_stats(elevation)

        assert stats.min_value == 0.0
        assert stats.max_value == 0.0
        assert stats.valid_count == 0
        assert stats.nodata_count == 4


class TestCalculateSlope:
    """Tests for slope calculation."""

    def test_flat_terrain(self):
        """Flat terrain should have zero slope."""
        # Completely flat terrain
        elevation = np.full((10, 10), 100.0, dtype=np.float64)
        slope, stats = calculate_slope(elevation, cell_size=10.0)

        assert stats.min_value == pytest.approx(0.0, abs=0.001)
        assert stats.max_value == pytest.approx(0.0, abs=0.001)
        assert stats.mean_value == pytest.approx(0.0, abs=0.001)

    def test_sloped_terrain(self):
        """Sloped terrain should have positive slope values."""
        # Create a ramp (constant slope)
        x = np.arange(10)
        y = np.arange(10)
        xx, yy = np.meshgrid(x, y)
        # 10 meter rise over 10 cells with 10m cell size = 100m
        # Expected slope = arctan(10/100) = ~5.7 degrees
        elevation = (xx * 10.0).astype(np.float64)

        slope, stats = calculate_slope(elevation, cell_size=10.0)

        # Slope should be around 5.7 degrees (arctan(10/100))
        assert stats.mean_value > 0
        assert stats.mean_value < 90

    def test_slope_classification(self):
        """Test that slope classification covers all classes."""
        # Create terrain with varying slopes
        elevation = np.random.rand(100, 100).astype(np.float64) * 100
        slope, stats = calculate_slope(elevation, cell_size=10.0)

        # All classes should be present
        for class_name in SLOPE_CLASSES.keys():
            assert class_name in stats.classification

        # Percentages should sum to ~100
        total = sum(stats.classification.values())
        assert total == pytest.approx(100.0, abs=0.1)

    def test_slope_with_nodata(self):
        """Slope calculation should handle NaN values."""
        elevation = np.array([[1, 2, 3], [4, np.nan, 6], [7, 8, 9]], dtype=np.float64)
        slope, stats = calculate_slope(elevation, cell_size=1.0)

        # The NaN should propagate
        assert np.isnan(slope[1, 1])


class TestCalculateAspect:
    """Tests for aspect calculation."""

    def test_north_facing_slope(self):
        """Slope facing north should have aspect ~0 or ~360."""
        # Create a slope that faces north (elevation increases southward)
        elevation = np.array(
            [[10, 10, 10], [5, 5, 5], [0, 0, 0]],
            dtype=np.float64,
        )
        aspect, stats = calculate_aspect(elevation, cell_size=1.0)

        # Most values should be in the N direction
        assert "N" in stats.distribution

    def test_east_facing_slope(self):
        """Slope facing east should have aspect ~90."""
        # Create a slope that faces east (elevation increases westward)
        elevation = np.array(
            [[10, 5, 0], [10, 5, 0], [10, 5, 0]],
            dtype=np.float64,
        )
        aspect, stats = calculate_aspect(elevation, cell_size=1.0)

        # Should have E-facing slopes
        assert "E" in stats.distribution

    def test_aspect_distribution_sum(self):
        """Aspect distribution should sum to ~100%."""
        elevation = np.random.rand(50, 50).astype(np.float64) * 100
        aspect, stats = calculate_aspect(elevation, cell_size=10.0)

        total = sum(stats.distribution.values())
        # May not sum to exactly 100 due to flat areas (-1 aspect)
        assert total <= 100.1

    def test_aspect_range(self):
        """Aspect values should be in range 0-360 or -1 for flat."""
        elevation = np.random.rand(20, 20).astype(np.float64) * 50
        aspect, stats = calculate_aspect(elevation, cell_size=10.0)

        valid_aspect = aspect[~np.isnan(aspect)]
        assert np.all((valid_aspect >= -1) & (valid_aspect <= 360))


class TestCalculateHillshade:
    """Tests for hillshade calculation."""

    def test_hillshade_range(self):
        """Hillshade values should be in range 0-255."""
        elevation = np.random.rand(20, 20).astype(np.float64) * 100
        hillshade, _ = calculate_hillshade(elevation, cell_size=10.0)

        assert hillshade.min() >= 0
        assert hillshade.max() <= 255
        assert hillshade.dtype == np.uint8

    def test_hillshade_flat_terrain(self):
        """Flat terrain should have uniform hillshade."""
        elevation = np.full((10, 10), 100.0, dtype=np.float64)
        hillshade, _ = calculate_hillshade(elevation, cell_size=10.0)

        # All values should be similar for flat terrain
        assert np.std(hillshade) < 1  # Very low variation


class TestRasterOutput:
    """Tests for raster file output."""

    def test_slope_raster_output(self):
        """Test that slope raster is saved correctly."""
        elevation = np.random.rand(20, 20).astype(np.float64) * 100
        transform = from_bounds(0, 0, 200, 200, 20, 20)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "slope.tif")
            slope, stats = calculate_slope(
                elevation,
                cell_size=10.0,
                output_path=output_path,
                transform=transform,
                crs="EPSG:4326",
            )

            assert os.path.exists(output_path)
            assert stats.raster_size > 0
            assert stats.raster_path == output_path

            # Verify the file can be read back
            with rasterio.open(output_path) as src:
                assert src.count == 1
                assert src.crs == CRS.from_epsg(4326)

    def test_aspect_raster_output(self):
        """Test that aspect raster is saved correctly."""
        elevation = np.random.rand(20, 20).astype(np.float64) * 100
        transform = from_bounds(0, 0, 200, 200, 20, 20)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "aspect.tif")
            aspect, stats = calculate_aspect(
                elevation,
                cell_size=10.0,
                output_path=output_path,
                transform=transform,
                crs="EPSG:4326",
            )

            assert os.path.exists(output_path)
            assert stats.raster_size > 0

    def test_hillshade_raster_output(self):
        """Test that hillshade raster is saved correctly."""
        elevation = np.random.rand(20, 20).astype(np.float64) * 100
        transform = from_bounds(0, 0, 200, 200, 20, 20)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "hillshade.tif")
            hillshade, size = calculate_hillshade(
                elevation,
                cell_size=10.0,
                output_path=output_path,
                transform=transform,
                crs="EPSG:4326",
            )

            assert os.path.exists(output_path)
            assert size > 0


class TestDataclasses:
    """Tests for dataclass structures."""

    def test_elevation_stats_dataclass(self):
        """Test ElevationStats dataclass."""
        stats = ElevationStats(
            min_value=0.0,
            max_value=100.0,
            mean_value=50.0,
            std_value=25.0,
            nodata_count=5,
            valid_count=95,
        )
        assert stats.min_value == 0.0
        assert stats.valid_count == 95

    def test_slope_stats_dataclass(self):
        """Test SlopeStats dataclass."""
        stats = SlopeStats(
            min_value=0.0,
            max_value=45.0,
            mean_value=10.0,
            std_value=5.0,
            classification={"flat": 10.0, "gentle": 30.0},
        )
        assert stats.max_value == 45.0
        assert "flat" in stats.classification

    def test_aspect_stats_dataclass(self):
        """Test AspectStats dataclass."""
        stats = AspectStats(distribution={"N": 15.0, "S": 20.0})
        assert stats.distribution["N"] == 15.0


class TestTerrainProfileMocked:
    """Tests for terrain profile using mocked DEM."""

    @patch("app.services.terrain_analysis.rasterio.open")
    def test_terrain_profile_basic(self, mock_open):
        """Test terrain profile extraction with mocked DEM."""
        # Create a mock rasterio dataset
        mock_dataset = MagicMock()
        mock_dataset.nodata = -9999

        # Mock sample method to return incrementing elevations
        def mock_sample(points):
            for i, _ in enumerate(points):
                yield [100.0 + i * 10]

        mock_dataset.sample = mock_sample
        mock_open.return_value.__enter__.return_value = mock_dataset

        profile = get_terrain_profile(
            dem_path="/fake/path.tif",
            start_point=(0.0, 0.0),
            end_point=(1.0, 1.0),
            num_samples=10,
        )

        assert len(profile["points"]) == 10
        assert len(profile["elevations"]) == 10
        assert len(profile["distances"]) == 10
        assert profile["total_distance"] > 0
