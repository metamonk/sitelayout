"""CRUD operations for asset placement."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPoint, mapping, shape
from sqlalchemy.orm import Session

from app.models.asset_placement import AssetPlacement, PlacementStatus
from app.schemas.asset_placement import AssetPlacementCreate, PlacementStatistics


class CRUDAssetPlacement:
    def get(self, db: Session, placement_id: UUID) -> Optional[AssetPlacement]:
        """Get an asset placement by ID."""
        return (
            db.query(AssetPlacement).filter(AssetPlacement.id == placement_id).first()
        )

    def get_by_project(
        self,
        db: Session,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AssetPlacement]:
        """Get all asset placements for a project."""
        return (
            db.query(AssetPlacement)
            .filter(AssetPlacement.project_id == project_id)
            .order_by(AssetPlacement.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_project(self, db: Session, project_id: UUID) -> int:
        """Get count of placements for a project."""
        return (
            db.query(AssetPlacement)
            .filter(AssetPlacement.project_id == project_id)
            .count()
        )

    def create(
        self,
        db: Session,
        project_id: UUID,
        user_id: UUID,
        placement_in: AssetPlacementCreate,
    ) -> AssetPlacement:
        """Create a new asset placement record."""
        # Convert placement area GeoJSON to geometry if provided
        placement_area_geom = None
        if placement_in.placement_area:
            shapely_geom = shape(placement_in.placement_area)
            placement_area_geom = from_shape(shapely_geom, srid=4326)

        db_obj = AssetPlacement(
            project_id=project_id,
            user_id=user_id,
            terrain_analysis_id=placement_in.terrain_analysis_id,
            name=placement_in.name,
            description=placement_in.description,
            status=PlacementStatus.PENDING,
            asset_width=placement_in.asset_width,
            asset_length=placement_in.asset_length,
            asset_count=placement_in.asset_count,
            assets_requested=placement_in.asset_count,
            grid_resolution=placement_in.grid_resolution,
            min_spacing=placement_in.min_spacing,
            max_slope=placement_in.max_slope,
            placement_area=placement_area_geom,
            optimization_criteria=placement_in.optimization_criteria,
            advanced_settings=placement_in.advanced_settings,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
        self,
        db: Session,
        db_obj: AssetPlacement,
        status: PlacementStatus,
        progress_percent: int = 0,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> AssetPlacement:
        """Update placement status and progress."""
        db_obj.status = status
        db_obj.progress_percent = progress_percent
        db_obj.current_step = current_step
        db_obj.error_message = error_message

        if status == PlacementStatus.PROCESSING and db_obj.started_at is None:
            db_obj.started_at = datetime.utcnow()
        elif status in (PlacementStatus.COMPLETED, PlacementStatus.FAILED):
            db_obj.completed_at = datetime.utcnow()

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_with_results(
        self,
        db: Session,
        db_obj: AssetPlacement,
        result: dict[str, Any],
    ) -> AssetPlacement:
        """Update placement with computed results."""
        if result.get("success", False):
            db_obj.status = PlacementStatus.COMPLETED
            db_obj.progress_percent = 100
            db_obj.current_step = "completed"
            db_obj.completed_at = datetime.utcnow()

            # Store placed assets as MultiPoint geometry
            if result.get("placed_positions"):
                points = result["placed_positions"]
                multipoint = MultiPoint(points)
                db_obj.placed_assets = from_shape(multipoint, srid=4326)

            # Store detailed placement information
            if result.get("placement_details"):
                db_obj.placement_details = result["placement_details"]

            # Statistics
            db_obj.assets_placed = result.get("assets_placed", 0)
            db_obj.placement_success_rate = result.get("placement_success_rate", 0.0)
            db_obj.grid_cells_total = result.get("grid_cells_total")
            db_obj.grid_cells_valid = result.get("grid_cells_valid")
            db_obj.grid_cells_excluded = result.get("grid_cells_excluded")

            # Optimization metrics
            db_obj.avg_slope = result.get("avg_slope")
            db_obj.avg_inter_asset_distance = result.get("avg_inter_asset_distance")
            db_obj.total_cut_fill_volume = result.get("total_cut_fill_volume")

            # Processing metadata
            db_obj.processing_time_seconds = result.get("processing_time")
            db_obj.memory_peak_mb = result.get("memory_peak_mb")
            db_obj.algorithm_iterations = result.get("algorithm_iterations")

        else:
            db_obj.status = PlacementStatus.FAILED
            db_obj.error_message = result.get("error_message", "Unknown error")
            db_obj.completed_at = datetime.utcnow()
            db_obj.processing_time_seconds = result.get("processing_time", 0.0)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_placement_details(
        self,
        db: Session,
        db_obj: AssetPlacement,
        placement_details: dict[str, Any],
    ) -> AssetPlacement:
        """Update placement details (for manual adjustments)."""
        db_obj.placement_details = placement_details

        # Update the MultiPoint geometry from the adjusted positions
        if placement_details and "assets" in placement_details:
            positions = [asset["position"] for asset in placement_details["assets"]]
            if positions:
                multipoint = MultiPoint(positions)
                db_obj.placed_assets = from_shape(multipoint, srid=4326)
                db_obj.assets_placed = len(positions)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, placement_id: UUID) -> bool:
        """Delete an asset placement."""
        placement = self.get(db, placement_id)
        if placement:
            db.delete(placement)
            db.commit()
            return True
        return False

    def to_response_dict(self, placement: AssetPlacement) -> dict[str, Any]:
        """Convert placement to response dictionary."""
        result = {
            "id": placement.id,
            "project_id": placement.project_id,
            "user_id": placement.user_id,
            "terrain_analysis_id": placement.terrain_analysis_id,
            "name": placement.name,
            "description": placement.description,
            "status": placement.status.value,
            "progress_percent": placement.progress_percent,
            "current_step": placement.current_step,
            "error_message": placement.error_message,
            "asset_width": placement.asset_width,
            "asset_length": placement.asset_length,
            "asset_count": placement.asset_count,
            "grid_resolution": placement.grid_resolution,
            "min_spacing": placement.min_spacing,
            "max_slope": placement.max_slope,
            "optimization_criteria": placement.optimization_criteria.value,
            "advanced_settings": placement.advanced_settings,
            "placement_area": None,
            "placed_assets": None,
            "placement_details": placement.placement_details,
            "statistics": None,
            "processing_time_seconds": placement.processing_time_seconds,
            "memory_peak_mb": placement.memory_peak_mb,
            "algorithm_iterations": placement.algorithm_iterations,
            "created_at": placement.created_at,
            "updated_at": placement.updated_at,
            "started_at": placement.started_at,
            "completed_at": placement.completed_at,
        }

        # Convert placement area to GeoJSON
        if placement.placement_area is not None:
            try:
                shape_obj = to_shape(placement.placement_area)
                result["placement_area"] = mapping(shape_obj)
            except Exception:
                pass

        # Convert placed assets to GeoJSON
        if placement.placed_assets is not None:
            try:
                shape_obj = to_shape(placement.placed_assets)
                result["placed_assets"] = mapping(shape_obj)
            except Exception:
                pass

        # Add statistics
        if placement.assets_placed is not None:
            result["statistics"] = PlacementStatistics(
                assets_placed=placement.assets_placed or 0,
                assets_requested=placement.assets_requested,
                placement_success_rate=placement.placement_success_rate or 0.0,
                grid_cells_total=placement.grid_cells_total,
                grid_cells_valid=placement.grid_cells_valid,
                grid_cells_excluded=placement.grid_cells_excluded,
                avg_slope=placement.avg_slope,
                avg_inter_asset_distance=placement.avg_inter_asset_distance,
                total_cut_fill_volume=placement.total_cut_fill_volume,
            ).model_dump()

        return result


# Singleton instance
asset_placement = CRUDAssetPlacement()
