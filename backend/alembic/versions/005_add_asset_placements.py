"""Add asset_placements table

Revision ID: 005
Revises: 004
Create Date: 2024-12-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create placement_status enum type
    placement_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="placementstatus",
        create_type=False,
    )
    placement_status.create(op.get_bind(), checkfirst=True)

    # Create optimization_criteria enum type
    optimization_criteria = postgresql.ENUM(
        "minimize_cut_fill",
        "maximize_flat_areas",
        "minimize_inter_asset_distance",
        "balanced",
        name="optimizationcriteria",
        create_type=False,
    )
    optimization_criteria.create(op.get_bind(), checkfirst=True)

    # Create asset_placements table
    op.create_table(
        "asset_placements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("terrain_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Metadata
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Status and progress
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", name="placementstatus"
            ),
            nullable=False,
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Configuration - Asset specifications
        sa.Column("asset_width", sa.Float(), nullable=False),
        sa.Column("asset_length", sa.Float(), nullable=False),
        sa.Column("asset_count", sa.Integer(), nullable=False),
        # Configuration - Grid
        sa.Column("grid_resolution", sa.Float(), nullable=False, server_default="5.0"),
        # Configuration - Constraints
        sa.Column("min_spacing", sa.Float(), nullable=False, server_default="10.0"),
        sa.Column("max_slope", sa.Float(), nullable=False, server_default="5.0"),
        # Placement area
        sa.Column("placement_area", Geometry("POLYGON", srid=4326), nullable=True),
        # Optimization settings
        sa.Column(
            "optimization_criteria",
            sa.Enum(
                "minimize_cut_fill",
                "maximize_flat_areas",
                "minimize_inter_asset_distance",
                "balanced",
                name="optimizationcriteria",
            ),
            nullable=False,
        ),
        sa.Column("advanced_settings", postgresql.JSONB(), nullable=True),
        # Results - Placed assets
        sa.Column("placed_assets", Geometry("MULTIPOINT", srid=4326), nullable=True),
        sa.Column("placement_details", postgresql.JSONB(), nullable=True),
        # Statistics
        sa.Column("assets_placed", sa.Integer(), nullable=True),
        sa.Column("assets_requested", sa.Integer(), nullable=False),
        sa.Column("placement_success_rate", sa.Float(), nullable=True),
        # Grid statistics
        sa.Column("grid_cells_total", sa.Integer(), nullable=True),
        sa.Column("grid_cells_valid", sa.Integer(), nullable=True),
        sa.Column("grid_cells_excluded", sa.Integer(), nullable=True),
        # Optimization metrics
        sa.Column("avg_slope", sa.Float(), nullable=True),
        sa.Column("avg_inter_asset_distance", sa.Float(), nullable=True),
        sa.Column("total_cut_fill_volume", sa.Float(), nullable=True),
        # Processing metadata
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("memory_peak_mb", sa.Float(), nullable=True),
        sa.Column("algorithm_iterations", sa.Integer(), nullable=True),
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
    )

    # Create indexes
    op.create_index(
        "ix_asset_placements_project_id", "asset_placements", ["project_id"]
    )
    op.create_index("ix_asset_placements_user_id", "asset_placements", ["user_id"])
    op.create_index("ix_asset_placements_status", "asset_placements", ["status"])

    # Create spatial indexes
    op.execute(
        "CREATE INDEX ix_asset_placements_area_geom ON asset_placements USING GIST (placement_area)"
    )
    op.execute(
        "CREATE INDEX ix_asset_placements_assets_geom ON asset_placements USING GIST (placed_assets)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_asset_placements_assets_geom")
    op.execute("DROP INDEX IF EXISTS ix_asset_placements_area_geom")
    op.drop_index("ix_asset_placements_status", table_name="asset_placements")
    op.drop_index("ix_asset_placements_user_id", table_name="asset_placements")
    op.drop_index("ix_asset_placements_project_id", table_name="asset_placements")

    # Drop table
    op.drop_table("asset_placements")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS optimizationcriteria")
    op.execute("DROP TYPE IF EXISTS placementstatus")
