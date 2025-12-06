"""Add road_networks table

Revision ID: 006
Revises: 005
Create Date: 2024-12-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create road_network_status enum type
    road_network_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="roadnetworkstatus",
        create_type=False,
    )
    road_network_status.create(op.get_bind(), checkfirst=True)

    # Create road_optimization_criteria enum type
    road_optimization_criteria = postgresql.ENUM(
        "minimal_length",
        "minimal_earthwork",
        "balanced",
        "minimal_grade",
        name="roadoptimizationcriteria",
        create_type=False,
    )
    road_optimization_criteria.create(op.get_bind(), checkfirst=True)

    # Create road_networks table
    op.create_table(
        "road_networks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("terrain_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_placement_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Metadata
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Status and progress
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", name="roadnetworkstatus"
            ),
            nullable=False,
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Configuration - Road specifications
        sa.Column("road_width", sa.Float(), nullable=False, server_default="6.0"),
        sa.Column("max_grade", sa.Float(), nullable=False, server_default="12.0"),
        sa.Column(
            "min_curve_radius", sa.Float(), nullable=False, server_default="15.0"
        ),
        # Configuration - Grid
        sa.Column("grid_resolution", sa.Float(), nullable=False, server_default="5.0"),
        # Optimization settings
        sa.Column(
            "optimization_criteria",
            sa.Enum(
                "minimal_length",
                "minimal_earthwork",
                "balanced",
                "minimal_grade",
                name="roadoptimizationcriteria",
            ),
            nullable=False,
        ),
        sa.Column("exclusion_buffer", sa.Float(), nullable=False, server_default="5.0"),
        # Entry point
        sa.Column("entry_point", Geometry("POINT", srid=4326), nullable=True),
        # Advanced settings
        sa.Column("advanced_settings", postgresql.JSONB(), nullable=True),
        # Results - Road geometries
        sa.Column(
            "road_centerlines", Geometry("MULTILINESTRING", srid=4326), nullable=True
        ),
        sa.Column("road_polygons", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("road_details", postgresql.JSONB(), nullable=True),
        # Statistics
        sa.Column("total_road_length", sa.Float(), nullable=True),
        sa.Column("total_segments", sa.Integer(), nullable=True),
        sa.Column("total_intersections", sa.Integer(), nullable=True),
        # Grade statistics
        sa.Column("avg_grade", sa.Float(), nullable=True),
        sa.Column("max_grade_actual", sa.Float(), nullable=True),
        sa.Column("grade_compliant", sa.Boolean(), nullable=True),
        # Earthwork estimates
        sa.Column("total_cut_volume", sa.Float(), nullable=True),
        sa.Column("total_fill_volume", sa.Float(), nullable=True),
        sa.Column("net_earthwork_volume", sa.Float(), nullable=True),
        # Connectivity metrics
        sa.Column("assets_connected", sa.Integer(), nullable=True),
        sa.Column("connectivity_rate", sa.Float(), nullable=True),
        # Processing metadata
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("memory_peak_mb", sa.Float(), nullable=True),
        sa.Column("algorithm_iterations", sa.Integer(), nullable=True),
        sa.Column("pathfinding_algorithm", sa.String(50), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["terrain_analysis_id"], ["terrain_analyses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["asset_placement_id"], ["asset_placements.id"], ondelete="SET NULL"
        ),
    )

    # Create indexes
    op.create_index("ix_road_networks_project_id", "road_networks", ["project_id"])
    op.create_index("ix_road_networks_user_id", "road_networks", ["user_id"])
    op.create_index("ix_road_networks_status", "road_networks", ["status"])

    # Create spatial indexes
    op.execute(
        "CREATE INDEX ix_road_networks_entry_point_geom ON road_networks USING GIST (entry_point)"
    )
    op.execute(
        "CREATE INDEX ix_road_networks_centerlines_geom ON road_networks USING GIST (road_centerlines)"
    )
    op.execute(
        "CREATE INDEX ix_road_networks_polygons_geom ON road_networks USING GIST (road_polygons)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_road_networks_polygons_geom")
    op.execute("DROP INDEX IF EXISTS ix_road_networks_centerlines_geom")
    op.execute("DROP INDEX IF EXISTS ix_road_networks_entry_point_geom")
    op.drop_index("ix_road_networks_status", table_name="road_networks")
    op.drop_index("ix_road_networks_user_id", table_name="road_networks")
    op.drop_index("ix_road_networks_project_id", table_name="road_networks")

    # Drop table
    op.drop_table("road_networks")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS roadoptimizationcriteria")
    op.execute("DROP TYPE IF EXISTS roadnetworkstatus")
