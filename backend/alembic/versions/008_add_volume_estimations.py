"""Add volume_estimations table for cut/fill volume estimation

Revision ID: 008
Revises: 007
Create Date: 2024-12-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create volume_estimation_status enum type
    volume_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        "cached",
        name="volumeestimationstatus",
        create_type=False,
    )
    volume_status.create(op.get_bind(), checkfirst=True)

    # Create foundation_type enum type
    foundation_type = postgresql.ENUM(
        "pad",
        "pier",
        "strip",
        "raft",
        name="foundationtype",
        create_type=False,
    )
    foundation_type.create(op.get_bind(), checkfirst=True)

    # Create volume_estimations table
    op.create_table(
        "volume_estimations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Optional references to source data
        sa.Column("terrain_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_placement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("road_network_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Status and progress
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                "cached",
                name="volumeestimationstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Configuration
        sa.Column("grid_resolution", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column(
            "default_foundation_type",
            sa.Enum("pad", "pier", "strip", "raft", name="foundationtype"),
            nullable=False,
            server_default="pad",
        ),
        sa.Column("road_width", sa.Float(), nullable=False, server_default="6.0"),
        # Asset volume totals
        sa.Column("total_asset_cut_volume_m3", sa.Float(), nullable=True),
        sa.Column("total_asset_fill_volume_m3", sa.Float(), nullable=True),
        sa.Column("total_asset_net_volume_m3", sa.Float(), nullable=True),
        sa.Column("assets_analyzed", sa.Integer(), nullable=False, server_default="0"),
        # Road volume totals
        sa.Column("total_road_cut_volume_m3", sa.Float(), nullable=True),
        sa.Column("total_road_fill_volume_m3", sa.Float(), nullable=True),
        sa.Column("total_road_net_volume_m3", sa.Float(), nullable=True),
        sa.Column(
            "road_segments_analyzed", sa.Integer(), nullable=False, server_default="0"
        ),
        # Project totals
        sa.Column("total_cut_volume_m3", sa.Float(), nullable=True),
        sa.Column("total_fill_volume_m3", sa.Float(), nullable=True),
        sa.Column("total_net_volume_m3", sa.Float(), nullable=True),
        sa.Column("cut_fill_ratio", sa.Float(), nullable=True),
        # Detailed breakdown stored as JSON
        sa.Column("asset_volumes_detail", postgresql.JSONB(), nullable=True),
        sa.Column("road_volumes_detail", postgresql.JSONB(), nullable=True),
        # 3D Visualization data
        sa.Column("visualization_data", postgresql.JSONB(), nullable=True),
        # Volumetric report data
        sa.Column("report_data", postgresql.JSONB(), nullable=True),
        # Analysis bounds
        sa.Column("analysis_bounds", Geometry("POLYGON", srid=4326), nullable=True),
        # DEM information
        sa.Column("dem_resolution", sa.Float(), nullable=True),
        # Processing metadata
        sa.Column(
            "total_cells_analyzed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("memory_peak_mb", sa.Float(), nullable=True),
        # Caching support
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("cache_valid_until", sa.DateTime(), nullable=True),
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
            ["terrain_analysis_id"], ["terrain_analyses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["asset_placement_id"], ["asset_placements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["road_network_id"], ["road_networks.id"], ondelete="SET NULL"
        ),
    )

    # Create indexes for faster lookups
    op.create_index(
        "ix_volume_estimations_project_id", "volume_estimations", ["project_id"]
    )
    op.create_index("ix_volume_estimations_status", "volume_estimations", ["status"])
    op.create_index(
        "ix_volume_estimations_input_hash", "volume_estimations", ["input_hash"]
    )
    op.create_index(
        "ix_volume_estimations_terrain_id",
        "volume_estimations",
        ["terrain_analysis_id"],
    )
    op.create_index(
        "ix_volume_estimations_placement_id",
        "volume_estimations",
        ["asset_placement_id"],
    )
    op.create_index(
        "ix_volume_estimations_road_id",
        "volume_estimations",
        ["road_network_id"],
    )

    # Create spatial index on analysis_bounds
    op.execute(
        "CREATE INDEX ix_volume_estimations_bounds_geom ON volume_estimations USING GIST (analysis_bounds)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_volume_estimations_bounds_geom")
    op.drop_index("ix_volume_estimations_road_id", table_name="volume_estimations")
    op.drop_index("ix_volume_estimations_placement_id", table_name="volume_estimations")
    op.drop_index("ix_volume_estimations_terrain_id", table_name="volume_estimations")
    op.drop_index("ix_volume_estimations_input_hash", table_name="volume_estimations")
    op.drop_index("ix_volume_estimations_status", table_name="volume_estimations")
    op.drop_index("ix_volume_estimations_project_id", table_name="volume_estimations")

    # Drop table
    op.drop_table("volume_estimations")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS volumeestimationstatus")
    op.execute("DROP TYPE IF EXISTS foundationtype")
