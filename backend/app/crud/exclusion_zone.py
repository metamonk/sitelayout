from typing import Any, Optional
from uuid import UUID

from geoalchemy2.functions import ST_Area, ST_Buffer, ST_Intersects, ST_Transform
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping, shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.exclusion_zone import ExclusionZone, ZoneSource, ZoneType


class CRUDExclusionZone:
    def get(self, db: Session, zone_id: UUID) -> Optional[ExclusionZone]:
        """Get an exclusion zone by ID."""
        return db.query(ExclusionZone).filter(ExclusionZone.id == zone_id).first()

    def get_by_project(
        self,
        db: Session,
        project_id: UUID,
        active_only: bool = True,
        zone_type: Optional[str] = None,
    ) -> list[ExclusionZone]:
        """Get all exclusion zones for a project."""
        query = db.query(ExclusionZone).filter(ExclusionZone.project_id == project_id)

        if active_only:
            query = query.filter(ExclusionZone.is_active.is_(True))

        if zone_type:
            query = query.filter(ExclusionZone.zone_type == ZoneType(zone_type))

        return query.order_by(ExclusionZone.created_at.desc()).all()

    def get_by_user(
        self, db: Session, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ExclusionZone]:
        """Get all exclusion zones for a user with pagination."""
        return (
            db.query(ExclusionZone)
            .filter(ExclusionZone.user_id == user_id)
            .order_by(ExclusionZone.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_count_by_project(self, db: Session, project_id: UUID) -> int:
        """Get total count of zones for a project."""
        return (
            db.query(ExclusionZone)
            .filter(ExclusionZone.project_id == project_id)
            .count()
        )

    def create(
        self,
        db: Session,
        project_id: UUID,
        user_id: UUID,
        name: str,
        zone_type: str,
        geometry: dict[str, Any],
        source: str = "drawn",
        description: Optional[str] = None,
        buffer_distance: Optional[float] = None,
        source_file_id: Optional[UUID] = None,
        fill_color: Optional[str] = None,
        stroke_color: Optional[str] = None,
        fill_opacity: Optional[float] = None,
    ) -> ExclusionZone:
        """Create a new exclusion zone."""
        # Convert GeoJSON to Shapely geometry
        shapely_geom = shape(geometry)
        geometry_type = geometry["type"]

        # Calculate area in square meters (transform to UTM for accuracy)
        # Area will be calculated after insert using PostGIS

        db_obj = ExclusionZone(
            project_id=project_id,
            user_id=user_id,
            name=name,
            description=description,
            zone_type=ZoneType(zone_type),
            source=ZoneSource(source),
            geometry=from_shape(shapely_geom, srid=4326),
            geometry_type=geometry_type,
            buffer_distance=buffer_distance,
            source_file_id=source_file_id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        # Calculate area using PostGIS (in square meters via UTM projection)
        if shapely_geom.geom_type in ["Polygon", "MultiPolygon"]:
            area_result = (
                db.query(
                    ST_Area(ST_Transform(ExclusionZone.geometry, 32618))  # UTM zone 18N
                )
                .filter(ExclusionZone.id == db_obj.id)
                .scalar()
            )
            if area_result:
                db_obj.area_sqm = float(area_result)
                db.add(db_obj)
                db.commit()
                db.refresh(db_obj)

        return db_obj

    def update(
        self,
        db: Session,
        db_obj: ExclusionZone,
        name: Optional[str] = None,
        description: Optional[str] = None,
        zone_type: Optional[str] = None,
        buffer_distance: Optional[float] = None,
        is_active: Optional[bool] = None,
        fill_color: Optional[str] = None,
        stroke_color: Optional[str] = None,
        fill_opacity: Optional[float] = None,
    ) -> ExclusionZone:
        """Update an exclusion zone."""
        if name is not None:
            db_obj.name = name
        if description is not None:
            db_obj.description = description
        if zone_type is not None:
            db_obj.zone_type = ZoneType(zone_type)
        if buffer_distance is not None:
            db_obj.buffer_distance = buffer_distance
        if is_active is not None:
            db_obj.is_active = is_active
        if fill_color is not None:
            db_obj.fill_color = fill_color
        if stroke_color is not None:
            db_obj.stroke_color = stroke_color
        if fill_opacity is not None:
            db_obj.fill_opacity = fill_opacity

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def apply_buffer(
        self, db: Session, db_obj: ExclusionZone, buffer_distance: float
    ) -> ExclusionZone:
        """Apply buffer to zone geometry."""
        # Use PostGIS ST_Buffer with geography for accurate meter-based buffer
        buffered = (
            db.query(
                ST_Buffer(
                    ST_Transform(ExclusionZone.geometry, 32618),  # Transform to UTM
                    buffer_distance,
                )
            )
            .filter(ExclusionZone.id == db_obj.id)
            .scalar()
        )

        if buffered:
            # Transform back to WGS84 and store
            buffered_wgs84 = db.query(
                ST_Transform(func.ST_SetSRID(buffered, 32618), 4326)
            ).scalar()

            db_obj.buffered_geometry = buffered_wgs84
            db_obj.buffer_distance = buffer_distance
            db_obj.buffer_applied = True

            # Recalculate area with buffer
            area_result = db.query(ST_Area(buffered)).scalar()
            if area_result:
                db_obj.area_sqm = float(area_result)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)

        return db_obj

    def remove_buffer(self, db: Session, db_obj: ExclusionZone) -> ExclusionZone:
        """Remove buffer from zone."""
        db_obj.buffered_geometry = None
        db_obj.buffer_applied = False

        # Recalculate area without buffer
        if db_obj.geometry:
            area_result = (
                db.query(ST_Area(ST_Transform(ExclusionZone.geometry, 32618)))
                .filter(ExclusionZone.id == db_obj.id)
                .scalar()
            )
            if area_result:
                db_obj.area_sqm = float(area_result)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def find_intersecting(
        self,
        db: Session,
        project_id: UUID,
        geometry: dict[str, Any],
        active_only: bool = True,
    ) -> list[ExclusionZone]:
        """Find zones that intersect with a given geometry."""
        shapely_geom = shape(geometry)
        geom_wkb = from_shape(shapely_geom, srid=4326)

        query = db.query(ExclusionZone).filter(
            ExclusionZone.project_id == project_id,
            ST_Intersects(
                func.coalesce(ExclusionZone.buffered_geometry, ExclusionZone.geometry),
                geom_wkb,
            ),
        )

        if active_only:
            query = query.filter(ExclusionZone.is_active.is_(True))

        return query.all()

    def delete(self, db: Session, zone_id: UUID) -> bool:
        """Delete an exclusion zone."""
        zone = self.get(db, zone_id)
        if zone:
            db.delete(zone)
            db.commit()
            return True
        return False

    def to_response_dict(self, zone: ExclusionZone) -> dict[str, Any]:
        """Convert exclusion zone to response dictionary with GeoJSON."""
        result = {
            "id": zone.id,
            "project_id": zone.project_id,
            "user_id": zone.user_id,
            "name": zone.name,
            "description": zone.description,
            "zone_type": zone.zone_type.value,
            "source": zone.source.value,
            "geometry_type": zone.geometry_type,
            "buffer_distance": zone.buffer_distance,
            "buffer_applied": zone.buffer_applied,
            "fill_color": zone.fill_color,
            "stroke_color": zone.stroke_color,
            "fill_opacity": zone.fill_opacity,
            "area_sqm": zone.area_sqm,
            "is_active": zone.is_active,
            "created_at": zone.created_at,
            "updated_at": zone.updated_at,
            "geometry": None,
            "buffered_geometry": None,
        }

        # Convert geometry to GeoJSON
        if zone.geometry is not None:
            try:
                shape_obj = to_shape(zone.geometry)
                result["geometry"] = mapping(shape_obj)
            except Exception:
                pass

        # Convert buffered geometry to GeoJSON if present
        if zone.buffered_geometry is not None:
            try:
                shape_obj = to_shape(zone.buffered_geometry)
                result["buffered_geometry"] = mapping(shape_obj)
            except Exception:
                pass

        return result


# Create singleton instance
exclusion_zone = CRUDExclusionZone()
