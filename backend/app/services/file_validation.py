"""
File validation service for KMZ/KML files.
Parses geographic files and validates geometry using Shapely.
"""

import hashlib
import io
import logging
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    mapping,
)
from shapely.validation import explain_validity, make_valid

logger = logging.getLogger("sitelayout.file_validation")

# KML namespace
KML_NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


@dataclass
class GeometryResult:
    """Result of geometry extraction and validation."""

    is_valid: bool
    geometry: Any  # Shapely geometry
    geometry_type: str
    feature_count: int
    wkt: str
    geojson: dict[str, Any]
    error_message: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of file validation."""

    is_valid: bool
    file_type: str  # "kml" or "kmz"
    geometry_result: Optional[GeometryResult] = None
    error_message: Optional[str] = None
    content_hash: Optional[str] = None


def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


def parse_kml_coordinates(coord_text: str) -> list[tuple[float, float, float]]:
    """
    Parse KML coordinate string into list of (lon, lat, alt) tuples.
    KML coordinates are in format: lon,lat,alt lon,lat,alt ...
    """
    coords: list[tuple[float, float, float]] = []
    if not coord_text:
        return coords

    # Split by whitespace and filter empty strings
    coord_strings = coord_text.strip().split()

    for coord_str in coord_strings:
        parts = coord_str.strip().split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) > 2 else 0.0
                coords.append((lon, lat, alt))
            except ValueError:
                continue

    return coords


def extract_geometry_from_kml_element(element: ET.Element) -> list[Any]:
    """Extract Shapely geometries from a KML element."""
    geometries = []

    # Find Point elements
    for point in element.findall(".//kml:Point/kml:coordinates", KML_NS):
        coords = parse_kml_coordinates(point.text or "")
        if coords:
            # Point only uses first coordinate
            lon, lat, _ = coords[0]
            geometries.append(Point(lon, lat))

    # Find LineString elements
    for linestring in element.findall(".//kml:LineString/kml:coordinates", KML_NS):
        coords = parse_kml_coordinates(linestring.text or "")
        if len(coords) >= 2:
            geometries.append(LineString([(c[0], c[1]) for c in coords]))

    # Find Polygon elements
    for polygon in element.findall(".//kml:Polygon", KML_NS):
        outer_coords = []
        inner_rings = []

        # Outer boundary
        outer_boundary = polygon.find(
            ".//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS
        )
        if outer_boundary is not None:
            coords = parse_kml_coordinates(outer_boundary.text or "")
            if len(coords) >= 4:
                outer_coords = [(c[0], c[1]) for c in coords]

        # Inner boundaries (holes)
        for inner in polygon.findall(
            ".//kml:innerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS
        ):
            coords = parse_kml_coordinates(inner.text or "")
            if len(coords) >= 4:
                inner_rings.append([(c[0], c[1]) for c in coords])

        if outer_coords:
            if inner_rings:
                geometries.append(Polygon(outer_coords, inner_rings))
            else:
                geometries.append(Polygon(outer_coords))

    return geometries


def extract_metadata_from_kml(root: ET.Element) -> tuple[Optional[str], Optional[str]]:
    """Extract name and description from KML root element."""
    name = None
    description = None

    # Try to find Document name first
    doc_name = root.find(".//kml:Document/kml:name", KML_NS)
    if doc_name is not None and doc_name.text:
        name = doc_name.text.strip()

    # Fall back to first Placemark name
    if not name:
        pm_name = root.find(".//kml:Placemark/kml:name", KML_NS)
        if pm_name is not None and pm_name.text:
            name = pm_name.text.strip()

    # Get description
    doc_desc = root.find(".//kml:Document/kml:description", KML_NS)
    if doc_desc is not None and doc_desc.text:
        description = doc_desc.text.strip()

    return name, description


def validate_and_fix_geometry(geometry: Any) -> tuple[Any, bool, Optional[str]]:
    """
    Validate geometry and attempt to fix if invalid.
    Returns (geometry, is_valid, error_message).
    """
    if geometry is None:
        return None, False, "No geometry found"

    if geometry.is_empty:
        return geometry, False, "Geometry is empty"

    if not geometry.is_valid:
        # Try to make it valid
        error_msg = explain_validity(geometry)
        logger.warning(f"Invalid geometry: {error_msg}. Attempting to fix.")

        try:
            fixed_geometry = make_valid(geometry)
            if fixed_geometry.is_valid:
                logger.info("Geometry fixed successfully")
                return fixed_geometry, True, None
            else:
                return geometry, False, f"Could not fix geometry: {error_msg}"
        except Exception as e:
            return geometry, False, f"Error fixing geometry: {str(e)}"

    return geometry, True, None


def parse_kml_content(kml_content: bytes) -> GeometryResult:
    """Parse KML content and extract geometry."""
    try:
        # Parse XML
        root = ET.fromstring(kml_content)

        # Extract metadata
        name, description = extract_metadata_from_kml(root)

        # Extract all geometries
        geometries = extract_geometry_from_kml_element(root)

        if not geometries:
            return GeometryResult(
                is_valid=False,
                geometry=None,
                geometry_type="None",
                feature_count=0,
                wkt="",
                geojson={},
                error_message="No geometries found in KML file",
                name=name,
                description=description,
            )

        # Combine geometries
        if len(geometries) == 1:
            combined = geometries[0]
        else:
            # Create appropriate multi-geometry or collection
            geom_types = set(type(g).__name__ for g in geometries)
            if geom_types == {"Point"}:
                combined = MultiPoint(geometries)
            elif geom_types == {"LineString"}:
                combined = MultiLineString(geometries)
            elif geom_types == {"Polygon"}:
                combined = MultiPolygon(geometries)
            else:
                combined = GeometryCollection(geometries)

        # Validate and fix geometry
        combined, is_valid, error_msg = validate_and_fix_geometry(combined)

        return GeometryResult(
            is_valid=is_valid,
            geometry=combined,
            geometry_type=type(combined).__name__,
            feature_count=len(geometries),
            wkt=combined.wkt if combined else "",
            geojson=mapping(combined) if combined else {},
            error_message=error_msg,
            name=name,
            description=description,
        )

    except ET.ParseError as e:
        return GeometryResult(
            is_valid=False,
            geometry=None,
            geometry_type="None",
            feature_count=0,
            wkt="",
            geojson={},
            error_message=f"Invalid KML XML: {str(e)}",
        )
    except Exception as e:
        logger.exception("Error parsing KML content")
        return GeometryResult(
            is_valid=False,
            geometry=None,
            geometry_type="None",
            feature_count=0,
            wkt="",
            geojson={},
            error_message=f"Error parsing KML: {str(e)}",
        )


def validate_file(file_path: Path, file_content: bytes) -> ValidationResult:
    """
    Validate a KMZ or KML file.

    Args:
        file_path: Path to the file (used to determine type)
        file_content: Raw file content

    Returns:
        ValidationResult with validation status and extracted geometry
    """
    file_extension = file_path.suffix.lower()
    content_hash = calculate_file_hash(file_content)

    if file_extension == ".kmz":
        return validate_kmz(file_content, content_hash)
    elif file_extension == ".kml":
        return validate_kml(file_content, content_hash)
    else:
        return ValidationResult(
            is_valid=False,
            file_type="unknown",
            error_message=f"Unsupported file type: {file_extension}",
            content_hash=content_hash,
        )


def validate_kml(kml_content: bytes, content_hash: str) -> ValidationResult:
    """Validate a KML file."""
    geometry_result = parse_kml_content(kml_content)

    return ValidationResult(
        is_valid=geometry_result.is_valid,
        file_type="kml",
        geometry_result=geometry_result,
        error_message=geometry_result.error_message,
        content_hash=content_hash,
    )


def validate_kmz(kmz_content: bytes, content_hash: str) -> ValidationResult:
    """Validate a KMZ file (zipped KML)."""
    try:
        # KMZ is a ZIP file containing a KML file
        with zipfile.ZipFile(io.BytesIO(kmz_content), "r") as zf:
            # Find the main KML file (usually doc.kml or *.kml)
            kml_files = [f for f in zf.namelist() if f.lower().endswith(".kml")]

            if not kml_files:
                return ValidationResult(
                    is_valid=False,
                    file_type="kmz",
                    error_message="No KML file found inside KMZ archive",
                    content_hash=content_hash,
                )

            # Prefer doc.kml if present, otherwise use first KML file
            main_kml = "doc.kml" if "doc.kml" in kml_files else kml_files[0]
            kml_content = zf.read(main_kml)

            geometry_result = parse_kml_content(kml_content)

            return ValidationResult(
                is_valid=geometry_result.is_valid,
                file_type="kmz",
                geometry_result=geometry_result,
                error_message=geometry_result.error_message,
                content_hash=content_hash,
            )

    except zipfile.BadZipFile:
        return ValidationResult(
            is_valid=False,
            file_type="kmz",
            error_message="Invalid KMZ file: not a valid ZIP archive",
            content_hash=content_hash,
        )
    except Exception as e:
        logger.exception("Error validating KMZ file")
        return ValidationResult(
            is_valid=False,
            file_type="kmz",
            error_message=f"Error processing KMZ file: {str(e)}",
            content_hash=content_hash,
        )
