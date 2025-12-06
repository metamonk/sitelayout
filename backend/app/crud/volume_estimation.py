"""CRUD operations for cut/fill volume estimation."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import box
from sqlalchemy.orm import Session

from app.models.volume_estimation import (
    FoundationType,
    VolumeEstimation,
    VolumeEstimationStatus,
)
from app.schemas.volume_estimation import (
    AssetVolumeDetail,
    AssetVolumeSummary,
    ProcessingMetadata,
    RoadSegmentVolumeDetail,
    RoadVolumeSummary,
    VolumeEstimationCreate,
    VolumeEstimationSummary,
)
from app.services.volume_estimation import VolumeEstimationResult

# Default cache duration
CACHE_DURATION = timedelta(days=7)


class CRUDVolumeEstimation:
    def get(self, db: Session, estimation_id: UUID) -> Optional[VolumeEstimation]:
        """Get a volume estimation by ID."""
        return (
            db.query(VolumeEstimation)
            .filter(VolumeEstimation.id == estimation_id)
            .first()
        )

    def get_by_project(
        self,
        db: Session,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[VolumeEstimation]:
        """Get all volume estimations for a project."""
        return (
            db.query(VolumeEstimation)
            .filter(VolumeEstimation.project_id == project_id)
            .order_by(VolumeEstimation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_project(self, db: Session, project_id: UUID) -> int:
        """Get count of estimations for a project."""
        return (
            db.query(VolumeEstimation)
            .filter(VolumeEstimation.project_id == project_id)
            .count()
        )

    def get_by_input_hash(
        self,
        db: Session,
        project_id: UUID,
        input_hash: str,
    ) -> Optional[VolumeEstimation]:
        """Get cached estimation by input hash."""
        return (
            db.query(VolumeEstimation)
            .filter(
                VolumeEstimation.project_id == project_id,
                VolumeEstimation.input_hash == input_hash,
                VolumeEstimation.status == VolumeEstimationStatus.COMPLETED,
                VolumeEstimation.cache_valid_until > datetime.utcnow(),
            )
            .first()
        )

    def create(
        self,
        db: Session,
        project_id: UUID,
        estimation_in: VolumeEstimationCreate,
    ) -> VolumeEstimation:
        """Create a new volume estimation record."""
        # Map foundation type string to enum
        foundation_type = FoundationType.PAD
        if estimation_in.default_foundation_type:
            try:
                foundation_type = FoundationType(
                    estimation_in.default_foundation_type.lower()
                )
            except ValueError:
                pass

        db_obj = VolumeEstimation(
            project_id=project_id,
            terrain_analysis_id=estimation_in.terrain_analysis_id,
            asset_placement_id=estimation_in.asset_placement_id,
            road_network_id=estimation_in.road_network_id,
            grid_resolution=estimation_in.grid_resolution,
            default_foundation_type=foundation_type,
            road_width=estimation_in.road_width,
            status=VolumeEstimationStatus.PENDING,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
        self,
        db: Session,
        db_obj: VolumeEstimation,
        status: VolumeEstimationStatus,
        progress_percent: int = 0,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> VolumeEstimation:
        """Update estimation status and progress."""
        db_obj.status = status
        db_obj.progress_percent = progress_percent
        db_obj.current_step = current_step
        db_obj.error_message = error_message

        if status == VolumeEstimationStatus.PROCESSING and db_obj.started_at is None:
            db_obj.started_at = datetime.utcnow()
        elif status in (
            VolumeEstimationStatus.COMPLETED,
            VolumeEstimationStatus.FAILED,
        ):
            db_obj.completed_at = datetime.utcnow()

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_with_results(
        self,
        db: Session,
        db_obj: VolumeEstimation,
        result: VolumeEstimationResult,
        input_hash: Optional[str] = None,
    ) -> VolumeEstimation:
        """Update estimation with computed results."""
        if result.success:
            db_obj.status = VolumeEstimationStatus.COMPLETED
            db_obj.progress_percent = 100
            db_obj.current_step = "completed"
            db_obj.completed_at = datetime.utcnow()

            # Asset totals
            db_obj.total_asset_cut_volume_m3 = result.total_asset_cut_volume_m3
            db_obj.total_asset_fill_volume_m3 = result.total_asset_fill_volume_m3
            db_obj.total_asset_net_volume_m3 = result.total_asset_net_volume_m3
            db_obj.assets_analyzed = len(result.asset_volumes)

            # Road totals
            db_obj.total_road_cut_volume_m3 = result.total_road_cut_volume_m3
            db_obj.total_road_fill_volume_m3 = result.total_road_fill_volume_m3
            db_obj.total_road_net_volume_m3 = result.total_road_net_volume_m3
            db_obj.road_segments_analyzed = len(result.road_volumes)

            # Project totals
            db_obj.total_cut_volume_m3 = result.total_cut_volume_m3
            db_obj.total_fill_volume_m3 = result.total_fill_volume_m3
            db_obj.total_net_volume_m3 = result.total_net_volume_m3
            db_obj.cut_fill_ratio = result.cut_fill_ratio

            # Store detailed breakdown as JSON
            db_obj.asset_volumes_detail = [  # type: ignore[assignment]
                {
                    "asset_id": av.asset_id,
                    "position": {
                        "longitude": av.position[0],
                        "latitude": av.position[1],
                    },
                    "foundation_type": av.foundation_type,
                    "cut_volume_m3": av.cut_volume_m3,
                    "fill_volume_m3": av.fill_volume_m3,
                    "net_volume_m3": av.net_volume_m3,
                    "footprint_area_m2": av.footprint_area_m2,
                    "max_cut_depth_m": av.max_cut_depth,
                    "max_fill_depth_m": av.max_fill_depth,
                }
                for av in result.asset_volumes
            ]

            db_obj.road_volumes_detail = [  # type: ignore[assignment]
                {
                    "segment_id": rv.segment_id,
                    "from_asset": rv.from_asset,
                    "to_asset": rv.to_asset,
                    "length_m": rv.road_length_m,
                    "area_m2": rv.road_area_m2,
                    "cut_volume_m3": rv.cut_volume_m3,
                    "fill_volume_m3": rv.fill_volume_m3,
                    "net_volume_m3": rv.net_volume_m3,
                    "avg_cut_depth_m": rv.avg_cut_depth,
                    "avg_fill_depth_m": rv.avg_fill_depth,
                }
                for rv in result.road_volumes
            ]

            # Visualization data
            db_obj.visualization_data = result.visualization_data

            # Set analysis bounds from visualization data
            if result.visualization_data and "bounds" in result.visualization_data:
                bounds = result.visualization_data["bounds"]
                bounds_geom = box(
                    bounds["minx"],
                    bounds["miny"],
                    bounds["maxx"],
                    bounds["maxy"],
                )
                db_obj.analysis_bounds = from_shape(bounds_geom, srid=4326)

            # Processing metadata
            db_obj.dem_resolution = result.dem_resolution
            db_obj.total_cells_analyzed = result.total_cells_analyzed
            db_obj.processing_time_seconds = result.processing_time
            db_obj.memory_peak_mb = result.memory_peak_mb

            # Caching
            if input_hash:
                db_obj.input_hash = input_hash
                db_obj.cache_valid_until = datetime.utcnow() + CACHE_DURATION

        else:
            db_obj.status = VolumeEstimationStatus.FAILED
            db_obj.error_message = result.error_message
            db_obj.completed_at = datetime.utcnow()
            db_obj.processing_time_seconds = result.processing_time

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, estimation_id: UUID) -> bool:
        """Delete a volume estimation."""
        estimation = self.get(db, estimation_id)
        if estimation:
            db.delete(estimation)
            db.commit()
            return True
        return False

    def to_response_dict(
        self, estimation: VolumeEstimation, include_details: bool = False
    ) -> dict[str, Any]:
        """Convert estimation to response dictionary."""
        result = {
            "id": estimation.id,
            "project_id": estimation.project_id,
            "terrain_analysis_id": estimation.terrain_analysis_id,
            "asset_placement_id": estimation.asset_placement_id,
            "road_network_id": estimation.road_network_id,
            "status": estimation.status.value,
            "progress_percent": estimation.progress_percent,
            "current_step": estimation.current_step,
            "error_message": estimation.error_message,
            "grid_resolution": estimation.grid_resolution,
            "default_foundation_type": estimation.default_foundation_type.value,
            "road_width": estimation.road_width,
            "summary": None,
            "asset_summary": None,
            "road_summary": None,
            "analysis_bounds": None,
            "processing_metadata": None,
            "has_asset_details": bool(estimation.asset_volumes_detail),
            "has_road_details": bool(estimation.road_volumes_detail),
            "has_visualization_data": bool(estimation.visualization_data),
            "has_report": bool(estimation.report_data),
            "created_at": estimation.created_at,
            "updated_at": estimation.updated_at,
            "started_at": estimation.started_at,
            "completed_at": estimation.completed_at,
        }

        # Add summary if completed
        if estimation.status == VolumeEstimationStatus.COMPLETED:
            cut_fill_ratio = estimation.cut_fill_ratio or 0.0
            if 0.8 <= cut_fill_ratio <= 1.2:
                balance_status = "Balanced"
            elif cut_fill_ratio > 1.2:
                balance_status = "Excess Cut"
            else:
                balance_status = "Excess Fill"

            result["summary"] = VolumeEstimationSummary(  # type: ignore[assignment]
                total_cut_volume_m3=estimation.total_cut_volume_m3 or 0.0,
                total_fill_volume_m3=estimation.total_fill_volume_m3 or 0.0,
                total_net_volume_m3=estimation.total_net_volume_m3 or 0.0,
                cut_fill_ratio=cut_fill_ratio,
                balance_status=balance_status,
            ).model_dump()

            result["asset_summary"] = AssetVolumeSummary(  # type: ignore[assignment]
                total_assets=estimation.assets_analyzed,
                total_cut_volume_m3=estimation.total_asset_cut_volume_m3 or 0.0,
                total_fill_volume_m3=estimation.total_asset_fill_volume_m3 or 0.0,
                total_net_volume_m3=estimation.total_asset_net_volume_m3 or 0.0,
            ).model_dump()

            result["road_summary"] = RoadVolumeSummary(  # type: ignore[assignment]
                total_segments=estimation.road_segments_analyzed,
                total_cut_volume_m3=estimation.total_road_cut_volume_m3 or 0.0,
                total_fill_volume_m3=estimation.total_road_fill_volume_m3 or 0.0,
                total_net_volume_m3=estimation.total_road_net_volume_m3 or 0.0,
            ).model_dump()

            # type: ignore[assignment]
            result["processing_metadata"] = ProcessingMetadata(
                dem_resolution_m=estimation.dem_resolution,
                grid_cell_size_m=estimation.grid_resolution,
                total_cells_analyzed=estimation.total_cells_analyzed,
                processing_time_seconds=estimation.processing_time_seconds,
                memory_peak_mb=estimation.memory_peak_mb,
            ).model_dump()

        # Convert bounds geometry to GeoJSON
        if estimation.analysis_bounds is not None:
            try:
                shape = to_shape(estimation.analysis_bounds)
                result["analysis_bounds"] = shape.__geo_interface__
            except Exception:
                pass

        # Include details if requested
        if include_details:
            if estimation.asset_volumes_detail:
                result["asset_volumes"] = [  # type: ignore[assignment]
                    AssetVolumeDetail(**av).model_dump()
                    for av in estimation.asset_volumes_detail
                ]
            if estimation.road_volumes_detail:
                result["road_volumes"] = [  # type: ignore[assignment]
                    RoadSegmentVolumeDetail(**rv).model_dump()
                    for rv in estimation.road_volumes_detail
                ]
            if estimation.visualization_data:
                # type: ignore[assignment]
                result["visualization_data"] = estimation.visualization_data

        return result


# Singleton instance
volume_estimation = CRUDVolumeEstimation()
