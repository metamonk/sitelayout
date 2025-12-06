"""CRUD operations for road network generation."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, MultiLineString, MultiPolygon, mapping, shape
from sqlalchemy.orm import Session

from app.models.road_network import RoadNetwork, RoadNetworkStatus
from app.schemas.road_network import RoadNetworkCreate, RoadNetworkStatistics


class CRUDRoadNetwork:
    def get(self, db: Session, network_id: UUID) -> Optional[RoadNetwork]:
        """Get a road network by ID."""
        return db.query(RoadNetwork).filter(RoadNetwork.id == network_id).first()

    def get_by_project(
        self,
        db: Session,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RoadNetwork]:
        """Get all road networks for a project."""
        return (
            db.query(RoadNetwork)
            .filter(RoadNetwork.project_id == project_id)
            .order_by(RoadNetwork.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_project(self, db: Session, project_id: UUID) -> int:
        """Get count of road networks for a project."""
        return (
            db.query(RoadNetwork).filter(RoadNetwork.project_id == project_id).count()
        )

    def create(
        self,
        db: Session,
        project_id: UUID,
        user_id: UUID,
        network_in: RoadNetworkCreate,
    ) -> RoadNetwork:
        """Create a new road network record."""
        # Convert entry point GeoJSON to geometry if provided
        entry_point_geom = None
        if network_in.entry_point:
            shapely_geom = shape(network_in.entry_point)
            entry_point_geom = from_shape(shapely_geom, srid=4326)

        db_obj = RoadNetwork(
            project_id=project_id,
            user_id=user_id,
            terrain_analysis_id=network_in.terrain_analysis_id,
            asset_placement_id=network_in.asset_placement_id,
            name=network_in.name,
            description=network_in.description,
            status=RoadNetworkStatus.PENDING,
            road_width=network_in.road_width,
            max_grade=network_in.max_grade,
            min_curve_radius=network_in.min_curve_radius,
            grid_resolution=network_in.grid_resolution,
            optimization_criteria=network_in.optimization_criteria,
            exclusion_buffer=network_in.exclusion_buffer,
            entry_point=entry_point_geom,
            advanced_settings=network_in.advanced_settings,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
        self,
        db: Session,
        db_obj: RoadNetwork,
        status: RoadNetworkStatus,
        progress_percent: int = 0,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> RoadNetwork:
        """Update road network status and progress."""
        db_obj.status = status
        db_obj.progress_percent = progress_percent
        db_obj.current_step = current_step
        db_obj.error_message = error_message

        if status == RoadNetworkStatus.PROCESSING and db_obj.started_at is None:
            db_obj.started_at = datetime.utcnow()
        elif status in (RoadNetworkStatus.COMPLETED, RoadNetworkStatus.FAILED):
            db_obj.completed_at = datetime.utcnow()

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_with_results(
        self,
        db: Session,
        db_obj: RoadNetwork,
        result: dict[str, Any],
    ) -> RoadNetwork:
        """Update road network with computed results."""
        if result.get("success", False):
            db_obj.status = RoadNetworkStatus.COMPLETED
            db_obj.progress_percent = 100
            db_obj.current_step = "completed"
            db_obj.completed_at = datetime.utcnow()

            # Store road centerlines as MultiLineString geometry
            if result.get("road_centerlines"):
                lines = result["road_centerlines"]
                if isinstance(lines, list):
                    # Convert list of coordinate lists to LineStrings
                    line_strings = []
                    for line in lines:
                        if len(line) >= 2:
                            line_strings.append(LineString(line))
                    if line_strings:
                        multiline = MultiLineString(line_strings)
                        db_obj.road_centerlines = from_shape(multiline, srid=4326)
                elif isinstance(lines, (MultiLineString, LineString)):
                    db_obj.road_centerlines = from_shape(lines, srid=4326)

            # Store road polygons (with width applied)
            if result.get("road_polygons"):
                polygons = result["road_polygons"]
                if isinstance(polygons, MultiPolygon):
                    db_obj.road_polygons = from_shape(polygons, srid=4326)

            # Store detailed road information
            if result.get("road_details"):
                db_obj.road_details = result["road_details"]

            # Statistics
            db_obj.total_road_length = result.get("total_road_length")
            db_obj.total_segments = result.get("total_segments")
            db_obj.total_intersections = result.get("total_intersections")

            # Grade statistics
            db_obj.avg_grade = result.get("avg_grade")
            db_obj.max_grade_actual = result.get("max_grade_actual")
            db_obj.grade_compliant = result.get("grade_compliant")

            # Earthwork
            db_obj.total_cut_volume = result.get("total_cut_volume")
            db_obj.total_fill_volume = result.get("total_fill_volume")
            db_obj.net_earthwork_volume = result.get("net_earthwork_volume")

            # Connectivity
            db_obj.assets_connected = result.get("assets_connected")
            db_obj.connectivity_rate = result.get("connectivity_rate")

            # Processing metadata
            db_obj.processing_time_seconds = result.get("processing_time")
            db_obj.memory_peak_mb = result.get("memory_peak_mb")
            db_obj.algorithm_iterations = result.get("algorithm_iterations")
            db_obj.pathfinding_algorithm = result.get("pathfinding_algorithm")

        else:
            db_obj.status = RoadNetworkStatus.FAILED
            db_obj.error_message = result.get("error_message", "Unknown error")
            db_obj.completed_at = datetime.utcnow()
            db_obj.processing_time_seconds = result.get("processing_time", 0.0)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_road_details(
        self,
        db: Session,
        db_obj: RoadNetwork,
        road_details: dict[str, Any],
    ) -> RoadNetwork:
        """Update road details (for manual adjustments)."""
        db_obj.road_details = road_details

        # Update the MultiLineString geometry from the adjusted coordinates
        if road_details and "segments" in road_details:
            line_strings = []
            for segment in road_details["segments"]:
                coords = segment.get("coordinates", [])
                if len(coords) >= 2:
                    # Use only lon, lat (first two values) for 2D geometry
                    coords_2d = [(c[0], c[1]) for c in coords]
                    line_strings.append(LineString(coords_2d))

            if line_strings:
                multiline = MultiLineString(line_strings)
                db_obj.road_centerlines = from_shape(multiline, srid=4326)
                db_obj.total_segments = len(line_strings)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, network_id: UUID) -> bool:
        """Delete a road network."""
        network = self.get(db, network_id)
        if network:
            db.delete(network)
            db.commit()
            return True
        return False

    def to_response_dict(self, network: RoadNetwork) -> dict[str, Any]:
        """Convert road network to response dictionary."""
        result = {
            "id": network.id,
            "project_id": network.project_id,
            "user_id": network.user_id,
            "terrain_analysis_id": network.terrain_analysis_id,
            "asset_placement_id": network.asset_placement_id,
            "name": network.name,
            "description": network.description,
            "status": network.status.value,
            "progress_percent": network.progress_percent,
            "current_step": network.current_step,
            "error_message": network.error_message,
            "road_width": network.road_width,
            "max_grade": network.max_grade,
            "min_curve_radius": network.min_curve_radius,
            "grid_resolution": network.grid_resolution,
            "optimization_criteria": network.optimization_criteria.value,
            "exclusion_buffer": network.exclusion_buffer,
            "advanced_settings": network.advanced_settings,
            "entry_point": None,
            "road_centerlines": None,
            "road_polygons": None,
            "road_details": network.road_details,
            "statistics": None,
            "processing_time_seconds": network.processing_time_seconds,
            "memory_peak_mb": network.memory_peak_mb,
            "algorithm_iterations": network.algorithm_iterations,
            "pathfinding_algorithm": network.pathfinding_algorithm,
            "created_at": network.created_at,
            "updated_at": network.updated_at,
            "started_at": network.started_at,
            "completed_at": network.completed_at,
        }

        # Convert entry point to GeoJSON
        if network.entry_point is not None:
            try:
                shape_obj = to_shape(network.entry_point)
                result["entry_point"] = mapping(shape_obj)
            except Exception:
                pass

        # Convert road centerlines to GeoJSON
        if network.road_centerlines is not None:
            try:
                shape_obj = to_shape(network.road_centerlines)
                result["road_centerlines"] = mapping(shape_obj)
            except Exception:
                pass

        # Convert road polygons to GeoJSON
        if network.road_polygons is not None:
            try:
                shape_obj = to_shape(network.road_polygons)
                result["road_polygons"] = mapping(shape_obj)
            except Exception:
                pass

        # Add statistics
        if network.total_road_length is not None:
            result["statistics"] = RoadNetworkStatistics(
                total_road_length=network.total_road_length or 0.0,
                total_segments=network.total_segments or 0,
                total_intersections=network.total_intersections or 0,
                avg_grade=network.avg_grade or 0.0,
                max_grade_actual=network.max_grade_actual or 0.0,
                grade_compliant=network.grade_compliant or False,
                total_cut_volume=network.total_cut_volume,
                total_fill_volume=network.total_fill_volume,
                net_earthwork_volume=network.net_earthwork_volume,
                assets_connected=network.assets_connected or 0,
                connectivity_rate=network.connectivity_rate or 0.0,
            ).model_dump()

        return result


# Singleton instance
road_network = CRUDRoadNetwork()
