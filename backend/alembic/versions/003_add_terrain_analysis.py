"""Add terrain_analyses table

Revision ID: 003
Revises: 002
Create Date: 2024-12-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create analysis_status enum type
    analysis_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        "cached",
        name="analysisstatus",
        create_type=False,
    )
    analysis_status.create(op.get_bind(), checkfirst=True)

    # Create terrain_analyses table
    op.create_table(
        "terrain_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Status and progress
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                "cached",
                name="analysisstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # DEM source info
        sa.Column("dem_source", sa.String(255), nullable=True),
        sa.Column("dem_resolution", sa.Float(), nullable=True),
        sa.Column("dem_crs", sa.String(50), nullable=True),
        # Analysis bounds
        sa.Column("analysis_bounds", Geometry("POLYGON", srid=4326), nullable=True),
        # Elevation statistics
        sa.Column("elevation_min", sa.Float(), nullable=True),
        sa.Column("elevation_max", sa.Float(), nullable=True),
        sa.Column("elevation_mean", sa.Float(), nullable=True),
        sa.Column("elevation_std", sa.Float(), nullable=True),
        # Slope statistics
        sa.Column("slope_min", sa.Float(), nullable=True),
        sa.Column("slope_max", sa.Float(), nullable=True),
        sa.Column("slope_mean", sa.Float(), nullable=True),
        sa.Column("slope_std", sa.Float(), nullable=True),
        sa.Column("slope_classification", postgresql.JSONB(), nullable=True),
        # Aspect distribution
        sa.Column("aspect_distribution", postgresql.JSONB(), nullable=True),
        # Raster file paths
        sa.Column("slope_raster_path", sa.String(500), nullable=True),
        sa.Column("aspect_raster_path", sa.String(500), nullable=True),
        sa.Column("hillshade_raster_path", sa.String(500), nullable=True),
        # File sizes
        sa.Column("slope_raster_size", sa.BigInteger(), nullable=True),
        sa.Column("aspect_raster_size", sa.BigInteger(), nullable=True),
        sa.Column("hillshade_raster_size", sa.BigInteger(), nullable=True),
        # Caching
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("cache_valid_until", sa.DateTime(), nullable=True),
        # Processing metadata
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("memory_peak_mb", sa.Float(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["uploaded_files.id"], ondelete="SET NULL"
        ),
    )

    # Create indexes
    op.create_index(
        "ix_terrain_analyses_project_id", "terrain_analyses", ["project_id"]
    )
    op.create_index("ix_terrain_analyses_status", "terrain_analyses", ["status"])
    op.create_index(
        "ix_terrain_analyses_input_hash", "terrain_analyses", ["input_hash"]
    )

    # Create spatial index on analysis_bounds
    op.execute(
        "CREATE INDEX ix_terrain_analyses_bounds_geom ON terrain_analyses USING GIST (analysis_bounds)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_terrain_analyses_bounds_geom")
    op.drop_index("ix_terrain_analyses_input_hash", table_name="terrain_analyses")
    op.drop_index("ix_terrain_analyses_status", table_name="terrain_analyses")
    op.drop_index("ix_terrain_analyses_project_id", table_name="terrain_analyses")

    # Drop table
    op.drop_table("terrain_analyses")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS analysisstatus")
