"""CRUD operations for terrain analysis."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy.orm import Session

from app.models.terrain_analysis import AnalysisStatus, TerrainAnalysis
from app.schemas.terrain import (
    AspectStatsResponse,
    ElevationStatsResponse,
    SlopeStatsResponse,
    TerrainAnalysisCreate,
)
from app.services.terrain_analysis import TerrainAnalysisResult

# Default cache duration
CACHE_DURATION = timedelta(days=7)


class CRUDTerrainAnalysis:
    def get(self, db: Session, analysis_id: UUID) -> Optional[TerrainAnalysis]:
        """Get a terrain analysis by ID."""
        return (
            db.query(TerrainAnalysis).filter(TerrainAnalysis.id == analysis_id).first()
        )

    def get_by_project(
        self,
        db: Session,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TerrainAnalysis]:
        """Get all terrain analyses for a project."""
        return (
            db.query(TerrainAnalysis)
            .filter(TerrainAnalysis.project_id == project_id)
            .order_by(TerrainAnalysis.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_project(self, db: Session, project_id: UUID) -> int:
        """Get count of analyses for a project."""
        return (
            db.query(TerrainAnalysis)
            .filter(TerrainAnalysis.project_id == project_id)
            .count()
        )

    def get_by_input_hash(
        self,
        db: Session,
        project_id: UUID,
        input_hash: str,
    ) -> Optional[TerrainAnalysis]:
        """Get cached analysis by input hash."""
        return (
            db.query(TerrainAnalysis)
            .filter(
                TerrainAnalysis.project_id == project_id,
                TerrainAnalysis.input_hash == input_hash,
                TerrainAnalysis.status == AnalysisStatus.COMPLETED,
                TerrainAnalysis.cache_valid_until > datetime.utcnow(),
            )
            .first()
        )

    def create(
        self,
        db: Session,
        project_id: UUID,
        analysis_in: TerrainAnalysisCreate,
    ) -> TerrainAnalysis:
        """Create a new terrain analysis record."""
        db_obj = TerrainAnalysis(
            project_id=project_id,
            source_file_id=analysis_in.source_file_id,
            status=AnalysisStatus.PENDING,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(
        self,
        db: Session,
        db_obj: TerrainAnalysis,
        status: AnalysisStatus,
        progress_percent: int = 0,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> TerrainAnalysis:
        """Update analysis status and progress."""
        db_obj.status = status
        db_obj.progress_percent = progress_percent
        db_obj.current_step = current_step
        db_obj.error_message = error_message

        if status == AnalysisStatus.PROCESSING and db_obj.started_at is None:
            db_obj.started_at = datetime.utcnow()
        elif status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED):
            db_obj.completed_at = datetime.utcnow()

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_with_results(
        self,
        db: Session,
        db_obj: TerrainAnalysis,
        result: TerrainAnalysisResult,
    ) -> TerrainAnalysis:
        """Update analysis with computed results."""
        if result.success:
            db_obj.status = AnalysisStatus.COMPLETED
            db_obj.progress_percent = 100
            db_obj.current_step = "completed"
            db_obj.completed_at = datetime.utcnow()

            # DEM info
            db_obj.dem_source = result.dem_source
            db_obj.dem_resolution = result.dem_resolution
            db_obj.dem_crs = result.dem_crs

            # Set analysis bounds if available
            if result.bounds_wkt:
                from shapely import wkt

                bounds_geom = wkt.loads(result.bounds_wkt)
                db_obj.analysis_bounds = from_shape(bounds_geom, srid=4326)

            # Elevation stats
            if result.elevation_stats:
                db_obj.elevation_min = result.elevation_stats.min_value
                db_obj.elevation_max = result.elevation_stats.max_value
                db_obj.elevation_mean = result.elevation_stats.mean_value
                db_obj.elevation_std = result.elevation_stats.std_value

            # Slope stats
            if result.slope_stats:
                db_obj.slope_min = result.slope_stats.min_value
                db_obj.slope_max = result.slope_stats.max_value
                db_obj.slope_mean = result.slope_stats.mean_value
                db_obj.slope_std = result.slope_stats.std_value
                db_obj.slope_classification = result.slope_stats.classification
                db_obj.slope_raster_path = result.slope_stats.raster_path
                db_obj.slope_raster_size = result.slope_stats.raster_size

            # Aspect stats
            if result.aspect_stats:
                db_obj.aspect_distribution = result.aspect_stats.distribution
                db_obj.aspect_raster_path = result.aspect_stats.raster_path
                db_obj.aspect_raster_size = result.aspect_stats.raster_size

            # Hillshade
            db_obj.hillshade_raster_path = result.hillshade_path
            db_obj.hillshade_raster_size = result.hillshade_size

            # Processing metadata
            db_obj.processing_time_seconds = result.processing_time
            db_obj.memory_peak_mb = result.memory_peak_mb
            db_obj.input_hash = result.input_hash
            db_obj.cache_valid_until = datetime.utcnow() + CACHE_DURATION

        else:
            db_obj.status = AnalysisStatus.FAILED
            db_obj.error_message = result.error_message
            db_obj.completed_at = datetime.utcnow()
            db_obj.processing_time_seconds = result.processing_time

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, analysis_id: UUID) -> bool:
        """Delete a terrain analysis."""
        analysis = self.get(db, analysis_id)
        if analysis:
            # TODO: Also delete associated raster files from disk
            db.delete(analysis)
            db.commit()
            return True
        return False

    def to_response_dict(self, analysis: TerrainAnalysis) -> dict[str, Any]:
        """Convert analysis to response dictionary."""
        result = {
            "id": analysis.id,
            "project_id": analysis.project_id,
            "source_file_id": analysis.source_file_id,
            "status": analysis.status.value,
            "progress_percent": analysis.progress_percent,
            "current_step": analysis.current_step,
            "error_message": analysis.error_message,
            "dem_source": analysis.dem_source,
            "dem_resolution": analysis.dem_resolution,
            "dem_crs": analysis.dem_crs,
            "analysis_bounds": None,
            "elevation_stats": None,
            "slope_stats": None,
            "aspect_stats": None,
            "slope_raster_available": bool(analysis.slope_raster_path),
            "aspect_raster_available": bool(analysis.aspect_raster_path),
            "hillshade_raster_available": bool(analysis.hillshade_raster_path),
            "processing_time_seconds": analysis.processing_time_seconds,
            "memory_peak_mb": analysis.memory_peak_mb,
            "is_cached": analysis.status == AnalysisStatus.CACHED,
            "created_at": analysis.created_at,
            "updated_at": analysis.updated_at,
            "started_at": analysis.started_at,
            "completed_at": analysis.completed_at,
        }

        # Convert bounds geometry to GeoJSON
        if analysis.analysis_bounds is not None:
            try:
                bounds_shape = to_shape(analysis.analysis_bounds)
                result["analysis_bounds"] = bounds_shape.__geo_interface__
            except Exception:
                pass

        # Add elevation stats
        if analysis.elevation_min is not None:
            result["elevation_stats"] = ElevationStatsResponse(  # type: ignore[assignment]
                min_value=analysis.elevation_min,
                max_value=analysis.elevation_max or 0.0,
                mean_value=analysis.elevation_mean or 0.0,
                std_value=analysis.elevation_std or 0.0,
            ).model_dump()

        # Add slope stats
        if analysis.slope_min is not None:
            result["slope_stats"] = SlopeStatsResponse(  # type: ignore[assignment]
                min_value=analysis.slope_min,
                max_value=analysis.slope_max or 0.0,
                mean_value=analysis.slope_mean or 0.0,
                std_value=analysis.slope_std or 0.0,
                classification=analysis.slope_classification or {},
            ).model_dump()

        # Add aspect stats
        if analysis.aspect_distribution:
            result["aspect_stats"] = AspectStatsResponse(  # type: ignore[assignment]
                distribution=analysis.aspect_distribution
            ).model_dump()

        return result


# Singleton instance
terrain_analysis = CRUDTerrainAnalysis()
