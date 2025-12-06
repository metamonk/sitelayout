"""Tests for export service functionality."""

import io
import json
import zipfile

from app.services.export_service import (
    CSVExporter,
    DXFExporter,
    ExportResult,
    ExportService,
    GeoJSONExporter,
    KMZExporter,
    PDFReportGenerator,
    ShapefileExporter,
)

# Sample test data
SAMPLE_PROJECT = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Test Project",
    "description": "A test project for exports",
    "status": "active",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-02T00:00:00",
}

SAMPLE_TERRAIN = {
    "status": "completed",
    "dem_source": "USGS",
    "dem_resolution": 10.0,
    "elevation_min": 100.0,
    "elevation_max": 500.0,
    "elevation_mean": 300.0,
    "slope_min": 0.0,
    "slope_max": 45.0,
    "slope_mean": 15.0,
    "slope_classification": {
        "flat": 10.0,
        "gentle": 30.0,
        "moderate": 40.0,
        "steep": 15.0,
        "very_steep": 5.0,
    },
}

SAMPLE_PLACEMENT = {
    "id": "placement-1",
    "name": "Test Placement",
    "status": "completed",
    "assets_placed": 5,
    "assets_requested": 5,
    "placement_success_rate": 100.0,
    "asset_width": 20.0,
    "asset_length": 40.0,
    "grid_resolution": 5.0,
    "min_spacing": 10.0,
    "max_slope": 5.0,
    "avg_slope": 2.5,
    "avg_inter_asset_distance": 50.0,
    "processing_time_seconds": 1.5,
    "placement_details": {
        "assets": [
            {
                "id": 1,
                "position": [-122.5, 37.5],
                "elevation": 150.0,
                "slope": 2.0,
                "rotation": 0.0,
            },
            {
                "id": 2,
                "position": [-122.4, 37.5],
                "elevation": 155.0,
                "slope": 2.5,
                "rotation": 45.0,
            },
            {
                "id": 3,
                "position": [-122.3, 37.5],
                "elevation": 160.0,
                "slope": 3.0,
                "rotation": 90.0,
            },
        ]
    },
}

SAMPLE_ROAD_NETWORK = {
    "id": "road-1",
    "name": "Test Roads",
    "status": "completed",
    "total_road_length": 500.0,
    "total_segments": 3,
    "road_width": 6.0,
    "max_grade": 12.0,
    "avg_grade": 5.0,
    "total_cut_volume": 100.0,
    "total_fill_volume": 80.0,
    "assets_connected": 3,
    "road_details": {
        "segments": [
            {
                "id": 1,
                "from_asset": 1,
                "to_asset": 2,
                "length_m": 200.0,
                "avg_grade": 5.0,
                "max_grade": 8.0,
                "coordinates": [
                    [-122.5, 37.5, 150],
                    [-122.45, 37.5, 152],
                    [-122.4, 37.5, 155],
                ],
            },
            {
                "id": 2,
                "from_asset": 2,
                "to_asset": 3,
                "length_m": 300.0,
                "avg_grade": 6.0,
                "max_grade": 10.0,
                "coordinates": [
                    [-122.4, 37.5, 155],
                    [-122.35, 37.5, 158],
                    [-122.3, 37.5, 160],
                ],
            },
        ]
    },
}

SAMPLE_EXCLUSION_ZONE = {
    "id": "zone-1",
    "name": "Wetland Area",
    "zone_type": "wetland",
    "description": "Protected wetland",
    "area_sqm": 5000.0,
    "buffer_distance": 10.0,
    "is_active": True,
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [-122.6, 37.4],
                [-122.5, 37.4],
                [-122.5, 37.5],
                [-122.6, 37.5],
                [-122.6, 37.4],
            ]
        ],
    },
}


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_success_result(self):
        """Test successful export result."""
        result = ExportResult(
            success=True,
            file_content=b"test content",
            filename="test.pdf",
            content_type="application/pdf",
        )
        assert result.success is True
        assert result.file_content == b"test content"
        assert result.filename == "test.pdf"
        assert result.content_type == "application/pdf"
        assert result.error_message is None

    def test_failure_result(self):
        """Test failed export result."""
        result = ExportResult(
            success=False,
            error_message="Export failed",
        )
        assert result.success is False
        assert result.error_message == "Export failed"
        assert result.file_content is None


class TestPDFReportGenerator:
    """Tests for PDF report generation."""

    def test_generate_basic_report(self):
        """Test basic PDF report generation."""
        generator = PDFReportGenerator()
        result = generator.generate_project_report(SAMPLE_PROJECT)

        assert result.success is True
        assert result.file_content is not None
        assert len(result.file_content) > 0
        assert result.content_type == "application/pdf"
        assert result.filename.endswith(".pdf")

    def test_generate_full_report(self):
        """Test PDF report with all sections."""
        generator = PDFReportGenerator()
        result = generator.generate_project_report(
            project=SAMPLE_PROJECT,
            terrain_analysis=SAMPLE_TERRAIN,
            asset_placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
            exclusion_zones=[SAMPLE_EXCLUSION_ZONE],
        )

        assert result.success is True
        assert result.file_content is not None
        assert len(result.file_content) > 1000  # PDF should have content

    def test_generate_report_without_data(self):
        """Test PDF report generation with minimal data."""
        generator = PDFReportGenerator()
        result = generator.generate_project_report(
            project={"name": "Minimal Project"},
        )

        assert result.success is True
        assert result.file_content is not None


class TestGeoJSONExporter:
    """Tests for GeoJSON export."""

    def test_export_asset_placements(self):
        """Test exporting assets to GeoJSON."""
        exporter = GeoJSONExporter()
        result = exporter.export_asset_placements([SAMPLE_PLACEMENT], "test_project")

        assert result.success is True
        assert result.content_type == "application/geo+json"

        # Parse and validate GeoJSON
        geojson = json.loads(result.file_content)
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 3  # 3 assets in sample

    def test_export_road_networks(self):
        """Test exporting roads to GeoJSON."""
        exporter = GeoJSONExporter()
        result = exporter.export_road_networks([SAMPLE_ROAD_NETWORK], "test_project")

        assert result.success is True

        geojson = json.loads(result.file_content)
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 2  # 2 road segments

        # Check geometry type
        assert geojson["features"][0]["geometry"]["type"] == "LineString"

    def test_export_exclusion_zones(self):
        """Test exporting zones to GeoJSON."""
        exporter = GeoJSONExporter()
        result = exporter.export_exclusion_zones(
            [SAMPLE_EXCLUSION_ZONE], "test_project"
        )

        assert result.success is True

        geojson = json.loads(result.file_content)
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 1

        # Check properties
        props = geojson["features"][0]["properties"]
        assert props["name"] == "Wetland Area"
        assert props["zone_type"] == "wetland"

    def test_export_combined(self):
        """Test exporting all layers to combined GeoJSON."""
        exporter = GeoJSONExporter()
        result = exporter.export_combined(
            placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
            exclusion_zones=[SAMPLE_EXCLUSION_ZONE],
            project_name="test_project",
        )

        assert result.success is True

        geojson = json.loads(result.file_content)
        assert geojson["type"] == "FeatureCollection"
        # 3 assets + 2 road segments + 1 zone = 6 features
        assert len(geojson["features"]) == 6

        # Check layer properties
        layers = set(f["properties"]["layer"] for f in geojson["features"])
        assert "assets" in layers
        assert "roads" in layers
        assert "exclusion_zones" in layers

    def test_export_empty_data(self):
        """Test exporting empty data."""
        exporter = GeoJSONExporter()
        result = exporter.export_asset_placements([], "test_project")

        assert result.success is True
        geojson = json.loads(result.file_content)
        assert len(geojson["features"]) == 0


class TestKMZExporter:
    """Tests for KMZ export."""

    def test_export_project(self):
        """Test exporting project to KMZ."""
        exporter = KMZExporter()
        result = exporter.export_project(
            project_name="test_project",
            placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
            exclusion_zones=[SAMPLE_EXCLUSION_ZONE],
        )

        assert result.success is True
        assert result.content_type == "application/vnd.google-earth.kmz"
        assert result.filename.endswith(".kmz")
        assert len(result.file_content) > 0

    def test_export_assets_only(self):
        """Test exporting only assets to KMZ."""
        exporter = KMZExporter()
        result = exporter.export_project(
            project_name="test_project",
            placements=[SAMPLE_PLACEMENT],
        )

        assert result.success is True
        assert len(result.file_content) > 0

    def test_export_empty_project(self):
        """Test exporting empty project to KMZ."""
        exporter = KMZExporter()
        result = exporter.export_project(project_name="empty_project")

        assert result.success is True


class TestShapefileExporter:
    """Tests for Shapefile export."""

    def test_export_assets(self):
        """Test exporting assets to Shapefile."""
        exporter = ShapefileExporter()
        result = exporter.export_assets([SAMPLE_PLACEMENT], "test_project")

        assert result.success is True
        assert result.content_type == "application/zip"
        assert result.filename.endswith(".zip")

        # Check zip contents
        with zipfile.ZipFile(io.BytesIO(result.file_content)) as zf:
            names = zf.namelist()
            # Should contain shapefile components
            assert any(n.endswith(".shp") for n in names)
            assert any(n.endswith(".shx") for n in names)
            assert any(n.endswith(".dbf") for n in names)
            assert any(n.endswith(".prj") for n in names)

    def test_export_roads(self):
        """Test exporting roads to Shapefile."""
        exporter = ShapefileExporter()
        result = exporter.export_roads([SAMPLE_ROAD_NETWORK], "test_project")

        assert result.success is True
        assert result.content_type == "application/zip"

    def test_export_zones(self):
        """Test exporting zones to Shapefile."""
        exporter = ShapefileExporter()
        result = exporter.export_zones([SAMPLE_EXCLUSION_ZONE], "test_project")

        assert result.success is True
        assert result.content_type == "application/zip"

    def test_export_empty_assets(self):
        """Test exporting empty assets fails gracefully."""
        exporter = ShapefileExporter()
        result = exporter.export_assets([], "test_project")

        assert result.success is False
        assert "No assets to export" in result.error_message


class TestCSVExporter:
    """Tests for CSV export."""

    def test_export_asset_list(self):
        """Test exporting asset list to CSV."""
        exporter = CSVExporter()
        result = exporter.export_asset_list([SAMPLE_PLACEMENT], "test_project")

        assert result.success is True
        assert result.content_type == "text/csv"
        assert result.filename.endswith(".csv")

        # Parse CSV content
        content = result.file_content.decode("utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 4  # Header + 3 assets

        # Check header
        assert "Asset ID" in lines[0]
        assert "Longitude" in lines[0]
        assert "Latitude" in lines[0]

    def test_export_road_segments(self):
        """Test exporting road segments to CSV."""
        exporter = CSVExporter()
        result = exporter.export_road_segments([SAMPLE_ROAD_NETWORK], "test_project")

        assert result.success is True
        assert result.content_type == "text/csv"

        content = result.file_content.decode("utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 segments

    def test_export_summary(self):
        """Test exporting project summary to CSV."""
        exporter = CSVExporter()
        result = exporter.export_summary(
            project=SAMPLE_PROJECT,
            terrain_analysis=SAMPLE_TERRAIN,
            asset_placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
            exclusion_zones=[SAMPLE_EXCLUSION_ZONE],
        )

        assert result.success is True
        assert result.content_type == "text/csv"

        content = result.file_content.decode("utf-8")
        assert "PROJECT SUMMARY" in content
        assert "TERRAIN ANALYSIS" in content
        assert "ASSET PLACEMENTS" in content
        assert "ROAD NETWORKS" in content
        assert "EXCLUSION ZONES" in content


class TestDXFExporter:
    """Tests for DXF export."""

    def test_export_project(self):
        """Test exporting project to DXF."""
        exporter = DXFExporter()
        result = exporter.export_project(
            project_name="test_project",
            placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
            exclusion_zones=[SAMPLE_EXCLUSION_ZONE],
        )

        assert result.success is True
        assert result.content_type == "application/dxf"
        assert result.filename.endswith(".dxf")
        assert len(result.file_content) > 0

    def test_export_assets_only(self):
        """Test exporting only assets to DXF."""
        exporter = DXFExporter()
        result = exporter.export_project(
            project_name="test_project",
            placements=[SAMPLE_PLACEMENT],
        )

        assert result.success is True
        assert len(result.file_content) > 0

    def test_export_empty_project(self):
        """Test exporting empty project to DXF."""
        exporter = DXFExporter()
        result = exporter.export_project(project_name="empty_project")

        assert result.success is True


class TestExportService:
    """Tests for main ExportService class."""

    def test_export_service_initialization(self):
        """Test ExportService initializes all exporters."""
        service = ExportService()

        assert hasattr(service, "pdf")
        assert hasattr(service, "geojson")
        assert hasattr(service, "kmz")
        assert hasattr(service, "shapefile")
        assert hasattr(service, "csv")
        assert hasattr(service, "dxf")

    def test_export_pdf_report(self):
        """Test PDF report through service."""
        service = ExportService()
        result = service.export_pdf_report(
            project=SAMPLE_PROJECT,
            terrain_analysis=SAMPLE_TERRAIN,
        )

        assert result.success is True
        assert result.content_type == "application/pdf"

    def test_export_geojson_assets(self):
        """Test GeoJSON asset export through service."""
        service = ExportService()
        result = service.export_geojson("assets", [SAMPLE_PLACEMENT], "test")

        assert result.success is True
        assert result.content_type == "application/geo+json"

    def test_export_geojson_roads(self):
        """Test GeoJSON road export through service."""
        service = ExportService()
        result = service.export_geojson("roads", [SAMPLE_ROAD_NETWORK], "test")

        assert result.success is True

    def test_export_geojson_zones(self):
        """Test GeoJSON zone export through service."""
        service = ExportService()
        result = service.export_geojson("zones", [SAMPLE_EXCLUSION_ZONE], "test")

        assert result.success is True

    def test_export_geojson_invalid_layer(self):
        """Test GeoJSON export with invalid layer."""
        service = ExportService()
        result = service.export_geojson("invalid", [], "test")

        assert result.success is False
        assert "Unknown layer" in result.error_message

    def test_export_geojson_combined(self):
        """Test combined GeoJSON export through service."""
        service = ExportService()
        result = service.export_geojson_combined(
            placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
            project_name="test",
        )

        assert result.success is True

    def test_export_kmz(self):
        """Test KMZ export through service."""
        service = ExportService()
        result = service.export_kmz(
            project_name="test",
            placements=[SAMPLE_PLACEMENT],
        )

        assert result.success is True
        assert result.content_type == "application/vnd.google-earth.kmz"

    def test_export_shapefile_assets(self):
        """Test Shapefile asset export through service."""
        service = ExportService()
        result = service.export_shapefile("assets", [SAMPLE_PLACEMENT], "test")

        assert result.success is True
        assert result.content_type == "application/zip"

    def test_export_shapefile_invalid_layer(self):
        """Test Shapefile export with invalid layer."""
        service = ExportService()
        result = service.export_shapefile("invalid", [], "test")

        assert result.success is False

    def test_export_csv_assets(self):
        """Test CSV asset export through service."""
        service = ExportService()
        result = service.export_csv("assets", [SAMPLE_PLACEMENT], "test")

        assert result.success is True
        assert result.content_type == "text/csv"

    def test_export_csv_summary(self):
        """Test CSV summary export through service."""
        service = ExportService()
        result = service.export_csv(
            "summary",
            SAMPLE_PROJECT,
            "test",
            terrain_analysis=SAMPLE_TERRAIN,
            asset_placements=[SAMPLE_PLACEMENT],
        )

        assert result.success is True

    def test_export_csv_invalid_type(self):
        """Test CSV export with invalid data type."""
        service = ExportService()
        result = service.export_csv("invalid", [], "test")

        assert result.success is False
        assert "Unknown data type" in result.error_message

    def test_export_dxf(self):
        """Test DXF export through service."""
        service = ExportService()
        result = service.export_dxf(
            project_name="test",
            placements=[SAMPLE_PLACEMENT],
            road_networks=[SAMPLE_ROAD_NETWORK],
        )

        assert result.success is True
        assert result.content_type == "application/dxf"


class TestGeoJSONCoordinateFormat:
    """Test coordinate handling in GeoJSON exports."""

    def test_asset_coordinates_format(self):
        """Test that asset coordinates are in correct format."""
        exporter = GeoJSONExporter()
        result = exporter.export_asset_placements([SAMPLE_PLACEMENT], "test")

        geojson = json.loads(result.file_content)
        feature = geojson["features"][0]

        coords = feature["geometry"]["coordinates"]
        assert len(coords) == 2  # [lon, lat]
        assert coords[0] == -122.5
        assert coords[1] == 37.5

    def test_road_coordinates_format(self):
        """Test that road coordinates are in correct format."""
        exporter = GeoJSONExporter()
        result = exporter.export_road_networks([SAMPLE_ROAD_NETWORK], "test")

        geojson = json.loads(result.file_content)
        feature = geojson["features"][0]

        coords = feature["geometry"]["coordinates"]
        assert len(coords) == 3  # 3 points in linestring
        assert len(coords[0]) == 2  # [lon, lat]


class TestExportMetadata:
    """Test metadata in export results."""

    def test_geojson_metadata(self):
        """Test that GeoJSON export includes metadata."""
        exporter = GeoJSONExporter()
        result = exporter.export_asset_placements([SAMPLE_PLACEMENT], "test")

        assert "feature_count" in result.metadata
        assert result.metadata["feature_count"] == 3

    def test_shapefile_metadata(self):
        """Test that Shapefile export includes metadata."""
        exporter = ShapefileExporter()
        result = exporter.export_assets([SAMPLE_PLACEMENT], "test")

        assert "feature_count" in result.metadata
        assert "format" in result.metadata
        assert result.metadata["format"] == "Shapefile"


class TestExportFilenames:
    """Test export filename generation."""

    def test_pdf_filename(self):
        """Test PDF filename generation."""
        generator = PDFReportGenerator()
        result = generator.generate_project_report({"name": "My Project"})

        assert result.filename == "My Project_report.pdf"

    def test_geojson_filename(self):
        """Test GeoJSON filename generation."""
        exporter = GeoJSONExporter()
        result = exporter.export_asset_placements([SAMPLE_PLACEMENT], "my_project")

        assert result.filename == "my_project_assets.geojson"

    def test_csv_filename(self):
        """Test CSV filename generation."""
        exporter = CSVExporter()
        result = exporter.export_asset_list([SAMPLE_PLACEMENT], "my_project")

        assert result.filename == "my_project_assets.csv"
