"""
Export service for generating reports and geospatial data exports.

Supports:
- PDF reports (ReportLab)
- GeoJSON exports (GeoPandas/native)
- KMZ exports for Google Earth (simplekml)
- Shapefile exports (Fiona/GeoPandas)
- CSV exports for tabular data
- DXF exports for CAD software (ezdxf)
"""

import io
import json
import logging
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import ezdxf  # type: ignore[import-untyped]
import geopandas as gpd
import simplekml  # type: ignore[import-untyped]
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import LETTER  # type: ignore[import-untyped]
from reportlab.lib.styles import (  # type: ignore[import-untyped]
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import inch  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from shapely.geometry import LineString, Point, shape

logger = logging.getLogger("sitelayout.export")


@dataclass
class ExportResult:
    """Result of an export operation."""

    success: bool
    file_content: Optional[bytes] = None
    filename: str = ""
    content_type: str = ""
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PDFReportGenerator:
    """Generate PDF reports for project data."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor("#1a365d"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=14,
                spaceBefore=20,
                spaceAfter=10,
                textColor=colors.HexColor("#2d3748"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Normal_Custom",
                parent=self.styles["Normal"],
                fontSize=10,
                spaceAfter=6,
            )
        )

    def generate_project_report(
        self,
        project: dict[str, Any],
        terrain_analysis: Optional[dict[str, Any]] = None,
        asset_placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Generate a comprehensive project report PDF."""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=LETTER,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72,
            )

            story = []

            # Title
            story.append(
                Paragraph(
                    f"Site Layout Report: {project.get('name', 'Untitled Project')}",
                    self.styles["ReportTitle"],
                )
            )
            story.append(Spacer(1, 12))

            # Project Overview
            story.append(Paragraph("Project Overview", self.styles["SectionHeader"]))
            overview_data = [
                ["Project Name:", project.get("name", "N/A")],
                ["Description:", project.get("description", "N/A")],
                ["Status:", project.get("status", "N/A")],
                ["Created:", str(project.get("created_at", "N/A"))],
            ]
            if project.get("location"):
                overview_data.append(["Location:", project.get("location")])

            story.append(self._create_info_table(overview_data))
            story.append(Spacer(1, 20))

            # Terrain Analysis Section
            if terrain_analysis:
                story.append(
                    Paragraph("Terrain Analysis", self.styles["SectionHeader"])
                )
                terrain_data = [
                    ["Analysis Status:", terrain_analysis.get("status", "N/A")],
                    ["DEM Source:", terrain_analysis.get("dem_source", "N/A")],
                    [
                        "Resolution:",
                        f"{terrain_analysis.get('dem_resolution', 'N/A')} m",
                    ],
                ]
                if terrain_analysis.get("elevation_min") is not None:
                    terrain_data.extend(
                        [
                            [
                                "Elevation Range:",
                                f"{terrain_analysis.get('elevation_min', 0):.1f} - "
                                f"{terrain_analysis.get('elevation_max', 0):.1f} m",
                            ],
                            [
                                "Mean Elevation:",
                                f"{terrain_analysis.get('elevation_mean', 0):.1f} m",
                            ],
                        ]
                    )
                if terrain_analysis.get("slope_mean") is not None:
                    terrain_data.extend(
                        [
                            [
                                "Average Slope:",
                                f"{terrain_analysis.get('slope_mean', 0):.1f}°",
                            ],
                            [
                                "Max Slope:",
                                f"{terrain_analysis.get('slope_max', 0):.1f}°",
                            ],
                        ]
                    )
                story.append(self._create_info_table(terrain_data))

                # Slope classification
                if terrain_analysis.get("slope_classification"):
                    story.append(Spacer(1, 10))
                    story.append(
                        Paragraph("Slope Classification", self.styles["Normal_Custom"])
                    )
                    slope_data = [["Category", "Percentage"]]
                    for category, percentage in terrain_analysis[
                        "slope_classification"
                    ].items():
                        slope_data.append(
                            [category.replace("_", " ").title(), f"{percentage:.1f}%"]
                        )
                    story.append(self._create_data_table(slope_data))

                story.append(Spacer(1, 20))

            # Asset Placements Section
            if asset_placements:
                story.append(
                    Paragraph("Asset Placements", self.styles["SectionHeader"])
                )
                for placement in asset_placements:
                    story.append(
                        Paragraph(
                            f"Placement: {placement.get('name', 'Unnamed')}",
                            self.styles["Heading3"],
                        )
                    )
                    placement_data = [
                        ["Status:", placement.get("status", "N/A")],
                        [
                            "Assets Placed:",
                            f"{placement.get('assets_placed', 0)} / "
                            f"{placement.get('assets_requested', 0)}",
                        ],
                        [
                            "Success Rate:",
                            f"{placement.get('placement_success_rate', 0):.1f}%",
                        ],
                        [
                            "Asset Dimensions:",
                            f"{placement.get('asset_width', 0)}m × "
                            f"{placement.get('asset_length', 0)}m",
                        ],
                        ["Grid Resolution:", f"{placement.get('grid_resolution', 0)}m"],
                        ["Min Spacing:", f"{placement.get('min_spacing', 0)}m"],
                        ["Max Slope:", f"{placement.get('max_slope', 0)}°"],
                    ]
                    if placement.get("avg_slope") is not None:
                        placement_data.append(
                            ["Average Slope:", f"{placement.get('avg_slope', 0):.2f}°"]
                        )
                    if placement.get("avg_inter_asset_distance") is not None:
                        placement_data.append(
                            [
                                "Avg Distance:",
                                f"{placement.get('avg_inter_asset_distance', 0):.1f}m",
                            ]
                        )
                    if placement.get("processing_time_seconds") is not None:
                        placement_data.append(
                            [
                                "Processing Time:",
                                f"{placement.get('processing_time_seconds', 0):.2f}s",
                            ]
                        )

                    story.append(self._create_info_table(placement_data))
                    story.append(Spacer(1, 10))
                story.append(Spacer(1, 20))

            # Road Networks Section
            if road_networks:
                story.append(Paragraph("Road Networks", self.styles["SectionHeader"]))
                for network in road_networks:
                    story.append(
                        Paragraph(
                            f"Network: {network.get('name', 'Unnamed')}",
                            self.styles["Heading3"],
                        )
                    )
                    network_data = [
                        ["Status:", network.get("status", "N/A")],
                        [
                            "Total Length:",
                            f"{network.get('total_road_length', 0):.1f}m",
                        ],
                        ["Road Segments:", str(network.get("total_segments", 0))],
                        ["Road Width:", f"{network.get('road_width', 0)}m"],
                        ["Max Grade:", f"{network.get('max_grade', 0)}%"],
                    ]
                    if network.get("avg_grade") is not None:
                        network_data.append(
                            ["Average Grade:", f"{network.get('avg_grade', 0):.1f}%"]
                        )
                    if network.get("total_cut_volume") is not None:
                        network_data.extend(
                            [
                                [
                                    "Cut Volume:",
                                    f"{network.get('total_cut_volume', 0):.1f} m³",
                                ],
                                [
                                    "Fill Volume:",
                                    f"{network.get('total_fill_volume', 0):.1f} m³",
                                ],
                            ]
                        )
                    if network.get("assets_connected") is not None:
                        network_data.append(
                            [
                                "Assets Connected:",
                                str(network.get("assets_connected", 0)),
                            ]
                        )

                    story.append(self._create_info_table(network_data))
                    story.append(Spacer(1, 10))
                story.append(Spacer(1, 20))

            # Exclusion Zones Section
            if exclusion_zones:
                story.append(Paragraph("Exclusion Zones", self.styles["SectionHeader"]))
                zones_data = [["Name", "Type", "Area (m²)", "Buffer (m)"]]
                for zone in exclusion_zones:
                    zones_data.append(
                        [
                            zone.get("name", "N/A"),
                            zone.get("zone_type", "N/A"),
                            (
                                f"{zone.get('area_sqm', 0):.1f}"
                                if zone.get("area_sqm")
                                else "N/A"
                            ),
                            (
                                f"{zone.get('buffer_distance', 0):.1f}"
                                if zone.get("buffer_distance")
                                else "N/A"
                            ),
                        ]
                    )
                story.append(self._create_data_table(zones_data))
                story.append(Spacer(1, 20))

            # Footer
            story.append(Spacer(1, 30))
            story.append(
                Paragraph(
                    f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    self.styles["Normal"],
                )
            )

            doc.build(story)

            return ExportResult(
                success=True,
                file_content=buffer.getvalue(),
                filename=f"{project.get('name', 'project')}_report.pdf",
                content_type="application/pdf",
                metadata={"pages": 1, "generated_at": datetime.now().isoformat()},
            )

        except Exception as e:
            logger.exception("Error generating PDF report")
            return ExportResult(
                success=False, error_message=f"PDF generation failed: {str(e)}"
            )

    def _create_info_table(self, data: list[list[str]]) -> Table:
        """Create a simple two-column info table."""
        table = Table(data, colWidths=[2 * inch, 4 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#4a5568")),
                ]
            )
        )
        return table

    def _create_data_table(self, data: list[list[str]]) -> Table:
        """Create a data table with headers."""
        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        return table


class GeoJSONExporter:
    """Export geospatial data to GeoJSON format."""

    def export_asset_placements(
        self,
        placements: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export asset placements to GeoJSON."""
        try:
            features = []
            for placement in placements:
                # Get placement details for individual assets
                details = placement.get("placement_details", {})
                assets = details.get("assets", [])

                for asset in assets:
                    position = asset.get("position", [])
                    if len(position) >= 2:
                        feature = {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": position[:2]},
                            "properties": {
                                "asset_id": asset.get("id"),
                                "placement_name": placement.get("name"),
                                "elevation": asset.get("elevation"),
                                "slope": asset.get("slope"),
                                "rotation": asset.get("rotation"),
                                "asset_width": placement.get("asset_width"),
                                "asset_length": placement.get("asset_length"),
                            },
                        }
                        features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "name": f"{project_name}_assets",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
                },
                "features": features,
            }

            content = json.dumps(geojson, indent=2).encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project_name}_assets.geojson",
                content_type="application/geo+json",
                metadata={"feature_count": len(features)},
            )

        except Exception as e:
            logger.exception("Error exporting to GeoJSON")
            return ExportResult(success=False, error_message=str(e))

    def export_road_networks(
        self,
        networks: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export road networks to GeoJSON."""
        try:
            features = []
            for network in networks:
                details = network.get("road_details", {})
                segments = details.get("segments", [])

                for segment in segments:
                    coords = segment.get("coordinates", [])
                    if coords:
                        feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[c[0], c[1]] for c in coords],
                            },
                            "properties": {
                                "segment_id": segment.get("id"),
                                "network_name": network.get("name"),
                                "length_m": segment.get("length_m"),
                                "avg_grade": segment.get("avg_grade"),
                                "max_grade": segment.get("max_grade"),
                                "from_asset": segment.get("from_asset"),
                                "to_asset": segment.get("to_asset"),
                                "road_width": network.get("road_width"),
                            },
                        }
                        features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "name": f"{project_name}_roads",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
                },
                "features": features,
            }

            content = json.dumps(geojson, indent=2).encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project_name}_roads.geojson",
                content_type="application/geo+json",
                metadata={"feature_count": len(features)},
            )

        except Exception as e:
            logger.exception("Error exporting roads to GeoJSON")
            return ExportResult(success=False, error_message=str(e))

    def export_exclusion_zones(
        self,
        zones: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export exclusion zones to GeoJSON."""
        try:
            features = []
            for zone in zones:
                geometry = zone.get("geometry")
                if geometry:
                    feature = {
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {
                            "name": zone.get("name"),
                            "zone_type": zone.get("zone_type"),
                            "description": zone.get("description"),
                            "area_sqm": zone.get("area_sqm"),
                            "buffer_distance": zone.get("buffer_distance"),
                            "is_active": zone.get("is_active"),
                        },
                    }
                    features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "name": f"{project_name}_exclusion_zones",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
                },
                "features": features,
            }

            content = json.dumps(geojson, indent=2).encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project_name}_exclusion_zones.geojson",
                content_type="application/geo+json",
                metadata={"feature_count": len(features)},
            )

        except Exception as e:
            logger.exception("Error exporting exclusion zones to GeoJSON")
            return ExportResult(success=False, error_message=str(e))

    def export_combined(
        self,
        placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
        project_name: str = "project",
    ) -> ExportResult:
        """Export all project data to a single GeoJSON file."""
        try:
            features = []

            # Add assets
            if placements:
                for placement in placements:
                    details = placement.get("placement_details", {})
                    for asset in details.get("assets", []):
                        position = asset.get("position", [])
                        if len(position) >= 2:
                            features.append(
                                {
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": position[:2],
                                    },
                                    "properties": {
                                        "layer": "assets",
                                        "asset_id": asset.get("id"),
                                        "name": placement.get("name"),
                                        **{
                                            k: v
                                            for k, v in asset.items()
                                            if k not in ["id", "position"]
                                        },
                                    },
                                }
                            )

            # Add roads
            if road_networks:
                for network in road_networks:
                    details = network.get("road_details", {})
                    for segment in details.get("segments", []):
                        coords = segment.get("coordinates", [])
                        if coords:
                            features.append(
                                {
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "LineString",
                                        "coordinates": [[c[0], c[1]] for c in coords],
                                    },
                                    "properties": {
                                        "layer": "roads",
                                        "segment_id": segment.get("id"),
                                        "name": network.get("name"),
                                        **{
                                            k: v
                                            for k, v in segment.items()
                                            if k not in ["id", "coordinates"]
                                        },
                                    },
                                }
                            )

            # Add exclusion zones
            if exclusion_zones:
                for zone in exclusion_zones:
                    geometry = zone.get("geometry")
                    if geometry:
                        features.append(
                            {
                                "type": "Feature",
                                "geometry": geometry,
                                "properties": {
                                    "layer": "exclusion_zones",
                                    **{
                                        k: v for k, v in zone.items() if k != "geometry"
                                    },
                                },
                            }
                        )

            geojson = {
                "type": "FeatureCollection",
                "name": f"{project_name}_all_layers",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
                },
                "features": features,
            }

            content = json.dumps(geojson, indent=2).encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project_name}_combined.geojson",
                content_type="application/geo+json",
                metadata={"feature_count": len(features)},
            )

        except Exception as e:
            logger.exception("Error exporting combined GeoJSON")
            return ExportResult(success=False, error_message=str(e))


class KMZExporter:
    """Export geospatial data to KMZ format for Google Earth."""

    def export_project(
        self,
        project_name: str,
        placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Export project data to KMZ format."""
        try:
            kml = simplekml.Kml(name=project_name)

            # Create folders for organization
            assets_folder = kml.newfolder(name="Assets")
            roads_folder = kml.newfolder(name="Roads")
            zones_folder = kml.newfolder(name="Exclusion Zones")

            # Style definitions
            asset_style = simplekml.Style()
            asset_style.iconstyle.icon.href = (
                "http://maps.google.com/mapfiles/kml/shapes/square.png"
            )
            asset_style.iconstyle.color = simplekml.Color.green
            asset_style.iconstyle.scale = 1.2

            road_style = simplekml.Style()
            road_style.linestyle.color = simplekml.Color.orange
            road_style.linestyle.width = 4

            zone_style = simplekml.Style()
            zone_style.polystyle.color = simplekml.Color.changealphaint(
                100, simplekml.Color.red
            )
            zone_style.linestyle.color = simplekml.Color.red
            zone_style.linestyle.width = 2

            # Add assets
            if placements:
                for placement in placements:
                    details = placement.get("placement_details", {})
                    for asset in details.get("assets", []):
                        position = asset.get("position", [])
                        if len(position) >= 2:
                            pnt = assets_folder.newpoint(
                                name=f"Asset {asset.get('id', '')}",
                                coords=[
                                    (
                                        position[0],
                                        position[1],
                                        asset.get("elevation", 0) or 0,
                                    )
                                ],
                            )
                            pnt.style = asset_style
                            dims = (
                                f"{placement.get('asset_width', 0)}m × "
                                f"{placement.get('asset_length', 0)}m"
                            )
                            pnt.description = (
                                f"Placement: {placement.get('name', 'N/A')}<br>"
                                f"Elevation: {asset.get('elevation', 'N/A')} m<br>"
                                f"Slope: {asset.get('slope', 'N/A')}°<br>"
                                f"Dimensions: {dims}"
                            )
                            if asset.get("elevation"):
                                pnt.altitudemode = (
                                    simplekml.AltitudeMode.relativetoground
                                )

            # Add road networks
            if road_networks:
                for network in road_networks:
                    details = network.get("road_details", {})
                    for segment in details.get("segments", []):
                        coords = segment.get("coordinates", [])
                        if coords:
                            line = roads_folder.newlinestring(
                                name=f"Road Segment {segment.get('id', '')}",
                                coords=[
                                    (c[0], c[1], c[2] if len(c) > 2 else 0)
                                    for c in coords
                                ],
                            )
                            line.style = road_style
                            line.description = (
                                f"Network: {network.get('name', 'N/A')}<br>"
                                f"Length: {segment.get('length_m', 'N/A')} m<br>"
                                f"Avg Grade: {segment.get('avg_grade', 'N/A')}%<br>"
                                f"Max Grade: {segment.get('max_grade', 'N/A')}%"
                            )

            # Add exclusion zones
            if exclusion_zones:
                for zone in exclusion_zones:
                    geometry = zone.get("geometry")
                    if geometry:
                        geom_type = geometry.get("type", "")
                        coords = geometry.get("coordinates", [])

                        if geom_type == "Polygon" and coords:
                            pol = zones_folder.newpolygon(name=zone.get("name", "Zone"))
                            # Convert coordinates to KML format
                            outer_ring = coords[0] if coords else []
                            pol.outerboundaryis = [(c[0], c[1]) for c in outer_ring]
                            pol.style = zone_style
                            pol.description = (
                                f"Type: {zone.get('zone_type', 'N/A')}<br>"
                                f"Area: {zone.get('area_sqm', 'N/A')} m²<br>"
                                f"Buffer: {zone.get('buffer_distance', 'N/A')} m"
                            )
                        elif geom_type == "MultiPolygon" and coords:
                            for i, polygon_coords in enumerate(coords):
                                pol = zones_folder.newpolygon(
                                    name=f"{zone.get('name', 'Zone')} ({i+1})"
                                )
                                outer_ring = polygon_coords[0] if polygon_coords else []
                                pol.outerboundaryis = [(c[0], c[1]) for c in outer_ring]
                                pol.style = zone_style

            # Save to KMZ (compressed KML)
            buffer = io.BytesIO()
            kml.savekmz(buffer)

            return ExportResult(
                success=True,
                file_content=buffer.getvalue(),
                filename=f"{project_name}.kmz",
                content_type="application/vnd.google-earth.kmz",
                metadata={"format": "KMZ", "generated_at": datetime.now().isoformat()},
            )

        except Exception as e:
            logger.exception("Error exporting to KMZ")
            return ExportResult(success=False, error_message=str(e))


class ShapefileExporter:
    """Export geospatial data to Shapefile format."""

    def export_assets(
        self,
        placements: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export asset placements to Shapefile."""
        try:
            # Build feature data
            records = []
            for placement in placements:
                details = placement.get("placement_details", {})
                for asset in details.get("assets", []):
                    position = asset.get("position", [])
                    if len(position) >= 2:
                        records.append(
                            {
                                "geometry": Point(position[0], position[1]),
                                "asset_id": asset.get("id"),
                                "placement": placement.get("name", "")[:50],
                                "elevation": asset.get("elevation"),
                                "slope": asset.get("slope"),
                                "rotation": asset.get("rotation"),
                                "width": placement.get("asset_width"),
                                "length": placement.get("asset_length"),
                            }
                        )

            if not records:
                return ExportResult(success=False, error_message="No assets to export")

            # Create GeoDataFrame
            gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

            # Write to temp directory and zip
            with tempfile.TemporaryDirectory() as tmpdir:
                shp_path = Path(tmpdir) / f"{project_name}_assets.shp"
                gdf.to_file(shp_path, driver="ESRI Shapefile")

                # Create zip with all shapefile components
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
                        file_path = shp_path.with_suffix(ext)
                        if file_path.exists():
                            zf.write(file_path, file_path.name)

            return ExportResult(
                success=True,
                file_content=buffer.getvalue(),
                filename=f"{project_name}_assets.zip",
                content_type="application/zip",
                metadata={"feature_count": len(records), "format": "Shapefile"},
            )

        except Exception as e:
            logger.exception("Error exporting to Shapefile")
            return ExportResult(success=False, error_message=str(e))

    def export_roads(
        self,
        networks: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export road networks to Shapefile."""
        try:
            records = []
            for network in networks:
                details = network.get("road_details", {})
                for segment in details.get("segments", []):
                    coords = segment.get("coordinates", [])
                    if len(coords) >= 2:
                        records.append(
                            {
                                "geometry": LineString([(c[0], c[1]) for c in coords]),
                                "segment_id": segment.get("id"),
                                "network": network.get("name", "")[:50],
                                "length_m": segment.get("length_m"),
                                "avg_grade": segment.get("avg_grade"),
                                "max_grade": segment.get("max_grade"),
                                "width": network.get("road_width"),
                            }
                        )

            if not records:
                return ExportResult(success=False, error_message="No roads to export")

            gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

            with tempfile.TemporaryDirectory() as tmpdir:
                shp_path = Path(tmpdir) / f"{project_name}_roads.shp"
                gdf.to_file(shp_path, driver="ESRI Shapefile")

                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
                        file_path = shp_path.with_suffix(ext)
                        if file_path.exists():
                            zf.write(file_path, file_path.name)

            return ExportResult(
                success=True,
                file_content=buffer.getvalue(),
                filename=f"{project_name}_roads.zip",
                content_type="application/zip",
                metadata={"feature_count": len(records), "format": "Shapefile"},
            )

        except Exception as e:
            logger.exception("Error exporting roads to Shapefile")
            return ExportResult(success=False, error_message=str(e))

    def export_zones(
        self,
        zones: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export exclusion zones to Shapefile."""
        try:
            records = []
            for zone in zones:
                geometry = zone.get("geometry")
                if geometry:
                    geom = shape(geometry)
                    records.append(
                        {
                            "geometry": geom,
                            "name": zone.get("name", "")[:50],
                            "zone_type": zone.get("zone_type", "")[:20],
                            "area_sqm": zone.get("area_sqm"),
                            "buffer_m": zone.get("buffer_distance"),
                            "is_active": zone.get("is_active"),
                        }
                    )

            if not records:
                return ExportResult(success=False, error_message="No zones to export")

            gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

            with tempfile.TemporaryDirectory() as tmpdir:
                shp_path = Path(tmpdir) / f"{project_name}_zones.shp"
                gdf.to_file(shp_path, driver="ESRI Shapefile")

                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
                        file_path = shp_path.with_suffix(ext)
                        if file_path.exists():
                            zf.write(file_path, file_path.name)

            return ExportResult(
                success=True,
                file_content=buffer.getvalue(),
                filename=f"{project_name}_zones.zip",
                content_type="application/zip",
                metadata={"feature_count": len(records), "format": "Shapefile"},
            )

        except Exception as e:
            logger.exception("Error exporting zones to Shapefile")
            return ExportResult(success=False, error_message=str(e))


class CSVExporter:
    """Export tabular data to CSV format."""

    def export_asset_list(
        self,
        placements: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export asset placement list to CSV."""
        try:
            import csv

            buffer = io.StringIO()
            writer = csv.writer(buffer)

            # Header
            writer.writerow(
                [
                    "Asset ID",
                    "Placement Name",
                    "Longitude",
                    "Latitude",
                    "Elevation (m)",
                    "Slope (°)",
                    "Rotation (°)",
                    "Width (m)",
                    "Length (m)",
                ]
            )

            # Data rows
            for placement in placements:
                details = placement.get("placement_details", {})
                for asset in details.get("assets", []):
                    position = asset.get("position", [None, None])
                    writer.writerow(
                        [
                            asset.get("id"),
                            placement.get("name"),
                            position[0] if position else None,
                            position[1] if len(position) > 1 else None,
                            asset.get("elevation"),
                            asset.get("slope"),
                            asset.get("rotation"),
                            placement.get("asset_width"),
                            placement.get("asset_length"),
                        ]
                    )

            content = buffer.getvalue().encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project_name}_assets.csv",
                content_type="text/csv",
                metadata={"format": "CSV"},
            )

        except Exception as e:
            logger.exception("Error exporting to CSV")
            return ExportResult(success=False, error_message=str(e))

    def export_road_segments(
        self,
        networks: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export road segment data to CSV."""
        try:
            import csv

            buffer = io.StringIO()
            writer = csv.writer(buffer)

            writer.writerow(
                [
                    "Segment ID",
                    "Network Name",
                    "From Asset",
                    "To Asset",
                    "Length (m)",
                    "Avg Grade (%)",
                    "Max Grade (%)",
                    "Cut Volume (m³)",
                    "Fill Volume (m³)",
                    "Width (m)",
                ]
            )

            for network in networks:
                details = network.get("road_details", {})
                for segment in details.get("segments", []):
                    writer.writerow(
                        [
                            segment.get("id"),
                            network.get("name"),
                            segment.get("from_asset"),
                            segment.get("to_asset"),
                            segment.get("length_m"),
                            segment.get("avg_grade"),
                            segment.get("max_grade"),
                            segment.get("cut_volume"),
                            segment.get("fill_volume"),
                            network.get("road_width"),
                        ]
                    )

            content = buffer.getvalue().encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project_name}_roads.csv",
                content_type="text/csv",
                metadata={"format": "CSV"},
            )

        except Exception as e:
            logger.exception("Error exporting roads to CSV")
            return ExportResult(success=False, error_message=str(e))

    def export_summary(
        self,
        project: dict[str, Any],
        terrain_analysis: Optional[dict[str, Any]] = None,
        asset_placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Export project summary to CSV."""
        try:
            import csv

            buffer = io.StringIO()
            writer = csv.writer(buffer)

            # Project info
            writer.writerow(["PROJECT SUMMARY"])
            writer.writerow(["Name", project.get("name")])
            writer.writerow(["Description", project.get("description")])
            writer.writerow(["Status", project.get("status")])
            writer.writerow([])

            # Terrain summary
            if terrain_analysis:
                writer.writerow(["TERRAIN ANALYSIS"])
                writer.writerow(["DEM Source", terrain_analysis.get("dem_source")])
                writer.writerow(
                    ["Resolution (m)", terrain_analysis.get("dem_resolution")]
                )
                writer.writerow(
                    ["Elevation Min (m)", terrain_analysis.get("elevation_min")]
                )
                writer.writerow(
                    ["Elevation Max (m)", terrain_analysis.get("elevation_max")]
                )
                writer.writerow(
                    ["Elevation Mean (m)", terrain_analysis.get("elevation_mean")]
                )
                writer.writerow(["Slope Mean (°)", terrain_analysis.get("slope_mean")])
                writer.writerow(["Slope Max (°)", terrain_analysis.get("slope_max")])
                writer.writerow([])

            # Asset summary
            if asset_placements:
                writer.writerow(["ASSET PLACEMENTS"])
                writer.writerow(
                    ["Name", "Assets Placed", "Success Rate (%)", "Avg Slope (°)"]
                )
                for placement in asset_placements:
                    writer.writerow(
                        [
                            placement.get("name"),
                            placement.get("assets_placed"),
                            placement.get("placement_success_rate"),
                            placement.get("avg_slope"),
                        ]
                    )
                writer.writerow([])

            # Road summary
            if road_networks:
                writer.writerow(["ROAD NETWORKS"])
                writer.writerow(
                    [
                        "Name",
                        "Total Length (m)",
                        "Segments",
                        "Avg Grade (%)",
                        "Cut Volume (m³)",
                        "Fill Volume (m³)",
                    ]
                )
                for network in road_networks:
                    writer.writerow(
                        [
                            network.get("name"),
                            network.get("total_road_length"),
                            network.get("total_segments"),
                            network.get("avg_grade"),
                            network.get("total_cut_volume"),
                            network.get("total_fill_volume"),
                        ]
                    )
                writer.writerow([])

            # Exclusion zones summary
            if exclusion_zones:
                writer.writerow(["EXCLUSION ZONES"])
                writer.writerow(["Name", "Type", "Area (m²)", "Buffer (m)"])
                for zone in exclusion_zones:
                    writer.writerow(
                        [
                            zone.get("name"),
                            zone.get("zone_type"),
                            zone.get("area_sqm"),
                            zone.get("buffer_distance"),
                        ]
                    )

            content = buffer.getvalue().encode("utf-8")

            return ExportResult(
                success=True,
                file_content=content,
                filename=f"{project.get('name', 'project')}_summary.csv",
                content_type="text/csv",
                metadata={"format": "CSV"},
            )

        except Exception as e:
            logger.exception("Error exporting summary to CSV")
            return ExportResult(success=False, error_message=str(e))


class DXFExporter:
    """Export data to DXF format for CAD software."""

    def export_project(
        self,
        project_name: str,
        placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Export project data to DXF format."""
        try:
            doc = ezdxf.new("R2018")
            msp = doc.modelspace()

            # Create layers
            doc.layers.add("ASSETS", color=3)  # Green
            doc.layers.add("ROADS", color=30)  # Orange
            doc.layers.add("EXCLUSION_ZONES", color=1)  # Red
            doc.layers.add("LABELS", color=7)  # White

            # Add assets as points/circles
            if placements:
                for placement in placements:
                    details = placement.get("placement_details", {})
                    asset_width = placement.get("asset_width", 10)
                    asset_length = placement.get("asset_length", 10)

                    for asset in details.get("assets", []):
                        position = asset.get("position", [])
                        if len(position) >= 2:
                            x, y = position[0], position[1]
                            # Scale from degrees to a reasonable CAD unit
                            # Using UTM-like scaling (multiply by ~111000 for meters)
                            scale = 111000  # rough meters per degree at equator
                            x_m, y_m = x * scale, y * scale

                            # Draw asset as rectangle
                            half_w = asset_width / 2
                            half_l = asset_length / 2
                            # Note: rotation not applied for simplicity
                            points = [
                                (x_m - half_w, y_m - half_l),
                                (x_m + half_w, y_m - half_l),
                                (x_m + half_w, y_m + half_l),
                                (x_m - half_w, y_m + half_l),
                                (x_m - half_w, y_m - half_l),
                            ]
                            msp.add_lwpolyline(points, dxfattribs={"layer": "ASSETS"})

                            # Add label
                            msp.add_text(
                                f"A{asset.get('id', '')}",
                                dxfattribs={
                                    "layer": "LABELS",
                                    "height": asset_width / 3,
                                    "insert": (x_m, y_m),
                                },
                            )

            # Add roads as polylines
            if road_networks:
                for network in road_networks:
                    details = network.get("road_details", {})
                    for segment in details.get("segments", []):
                        coords = segment.get("coordinates", [])
                        if len(coords) >= 2:
                            scale = 111000
                            points = [(c[0] * scale, c[1] * scale) for c in coords]
                            msp.add_lwpolyline(points, dxfattribs={"layer": "ROADS"})

            # Add exclusion zones as polygons
            if exclusion_zones:
                for zone in exclusion_zones:
                    geometry = zone.get("geometry")
                    if geometry:
                        geom_type = geometry.get("type", "")
                        coords = geometry.get("coordinates", [])

                        if geom_type == "Polygon" and coords:
                            scale = 111000
                            outer_ring = coords[0] if coords else []
                            if outer_ring:
                                points = [
                                    (c[0] * scale, c[1] * scale) for c in outer_ring
                                ]
                                msp.add_lwpolyline(
                                    points,
                                    close=True,
                                    dxfattribs={"layer": "EXCLUSION_ZONES"},
                                )

            # Save to buffer (DXF needs StringIO, then encode to bytes)
            string_buffer = io.StringIO()
            doc.write(string_buffer)

            return ExportResult(
                success=True,
                file_content=string_buffer.getvalue().encode("utf-8"),
                filename=f"{project_name}.dxf",
                content_type="application/dxf",
                metadata={"format": "DXF", "version": "R2018"},
            )

        except Exception as e:
            logger.exception("Error exporting to DXF")
            return ExportResult(success=False, error_message=str(e))


class ExportService:
    """Main export service coordinating all export formats."""

    def __init__(self):
        self.pdf = PDFReportGenerator()
        self.geojson = GeoJSONExporter()
        self.kmz = KMZExporter()
        self.shapefile = ShapefileExporter()
        self.csv = CSVExporter()
        self.dxf = DXFExporter()

    def export_pdf_report(
        self,
        project: dict[str, Any],
        terrain_analysis: Optional[dict[str, Any]] = None,
        asset_placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Generate PDF project report."""
        return self.pdf.generate_project_report(
            project, terrain_analysis, asset_placements, road_networks, exclusion_zones
        )

    def export_geojson(
        self,
        layer: str,
        data: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export specific layer to GeoJSON."""
        if layer == "assets":
            return self.geojson.export_asset_placements(data, project_name)
        elif layer == "roads":
            return self.geojson.export_road_networks(data, project_name)
        elif layer == "zones":
            return self.geojson.export_exclusion_zones(data, project_name)
        else:
            return ExportResult(success=False, error_message=f"Unknown layer: {layer}")

    def export_geojson_combined(
        self,
        placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
        project_name: str = "project",
    ) -> ExportResult:
        """Export all layers to combined GeoJSON."""
        return self.geojson.export_combined(
            placements, road_networks, exclusion_zones, project_name
        )

    def export_kmz(
        self,
        project_name: str,
        placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Export to KMZ for Google Earth."""
        return self.kmz.export_project(
            project_name, placements, road_networks, exclusion_zones
        )

    def export_shapefile(
        self,
        layer: str,
        data: list[dict[str, Any]],
        project_name: str = "project",
    ) -> ExportResult:
        """Export specific layer to Shapefile."""
        if layer == "assets":
            return self.shapefile.export_assets(data, project_name)
        elif layer == "roads":
            return self.shapefile.export_roads(data, project_name)
        elif layer == "zones":
            return self.shapefile.export_zones(data, project_name)
        else:
            return ExportResult(success=False, error_message=f"Unknown layer: {layer}")

    def export_csv(
        self,
        data_type: str,
        data: Any,
        project_name: str = "project",
        **kwargs: Any,
    ) -> ExportResult:
        """Export to CSV format."""
        if data_type == "assets":
            return self.csv.export_asset_list(data, project_name)
        elif data_type == "roads":
            return self.csv.export_road_segments(data, project_name)
        elif data_type == "summary":
            return self.csv.export_summary(
                data,
                terrain_analysis=kwargs.get("terrain_analysis"),
                asset_placements=kwargs.get("asset_placements"),
                road_networks=kwargs.get("road_networks"),
                exclusion_zones=kwargs.get("exclusion_zones"),
            )
        else:
            return ExportResult(
                success=False, error_message=f"Unknown data type: {data_type}"
            )

    def export_dxf(
        self,
        project_name: str,
        placements: Optional[list[dict[str, Any]]] = None,
        road_networks: Optional[list[dict[str, Any]]] = None,
        exclusion_zones: Optional[list[dict[str, Any]]] = None,
    ) -> ExportResult:
        """Export to DXF for CAD software."""
        return self.dxf.export_project(
            project_name, placements, road_networks, exclusion_zones
        )
