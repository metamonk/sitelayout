"""Add performance indexes

Revision ID: 007
Revises: 006
Create Date: 2025-12-06

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing index for projects.user_id - critical for user's projects listing
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    # Add composite index for common project listing query (user_id + created_at)
    op.create_index(
        "ix_projects_user_id_created_at",
        "projects",
        ["user_id", "created_at"],
    )

    # Add composite index for terrain analysis lookup by project and status
    op.create_index(
        "ix_terrain_analyses_project_status",
        "terrain_analyses",
        ["project_id", "status"],
    )

    # Add composite index for asset placements lookup by project and status
    op.create_index(
        "ix_asset_placements_project_status",
        "asset_placements",
        ["project_id", "status"],
    )

    # Add composite index for exclusion zones by project and active status
    op.create_index(
        "ix_exclusion_zones_project_active",
        "exclusion_zones",
        ["project_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_exclusion_zones_project_active", table_name="exclusion_zones")
    op.drop_index("ix_asset_placements_project_status", table_name="asset_placements")
    op.drop_index("ix_terrain_analyses_project_status", table_name="terrain_analyses")
    op.drop_index("ix_projects_user_id_created_at", table_name="projects")
    op.drop_index("ix_projects_user_id", table_name="projects")
