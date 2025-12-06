"""Add exclusion_zones table

Revision ID: 004
Revises: 003
Create Date: 2024-12-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create zone_type enum
    zone_type = postgresql.ENUM(
        "wetland",
        "easement",
        "stream_buffer",
        "setback",
        "custom",
        name="zonetype",
        create_type=False,
    )
    zone_type.create(op.get_bind(), checkfirst=True)

    # Create zone_source enum
    zone_source = postgresql.ENUM(
        "imported",
        "drawn",
        name="zonesource",
        create_type=False,
    )
    zone_source.create(op.get_bind(), checkfirst=True)

    # Create exclusion_zones table
    op.create_table(
        "exclusion_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Zone metadata
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "zone_type",
            sa.Enum(
                "wetland",
                "easement",
                "stream_buffer",
                "setback",
                "custom",
                name="zonetype",
            ),
            nullable=False,
        ),
        sa.Column(
            "source", sa.Enum("imported", "drawn", name="zonesource"), nullable=False
        ),
        # Geometry
        sa.Column("geometry", Geometry("GEOMETRY", srid=4326), nullable=False),
        sa.Column("geometry_type", sa.String(50), nullable=False),
        # Buffer configuration
        sa.Column("buffer_distance", sa.Float(), nullable=True),
        sa.Column(
            "buffer_applied", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("buffered_geometry", Geometry("GEOMETRY", srid=4326), nullable=True),
        # Source file reference
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Styling
        sa.Column("fill_color", sa.String(20), nullable=True),
        sa.Column("stroke_color", sa.String(20), nullable=True),
        sa.Column("fill_opacity", sa.Float(), nullable=True),
        # Area
        sa.Column("area_sqm", sa.Float(), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["uploaded_files.id"], ondelete="SET NULL"
        ),
    )

    # Create indexes
    op.create_index("ix_exclusion_zones_project_id", "exclusion_zones", ["project_id"])
    op.create_index("ix_exclusion_zones_user_id", "exclusion_zones", ["user_id"])
    op.create_index("ix_exclusion_zones_zone_type", "exclusion_zones", ["zone_type"])
    op.create_index("ix_exclusion_zones_is_active", "exclusion_zones", ["is_active"])

    # Create spatial indexes
    op.execute(
        "CREATE INDEX ix_exclusion_zones_geometry ON exclusion_zones USING GIST (geometry)"
    )
    op.execute(
        "CREATE INDEX ix_exclusion_zones_buffered_geometry ON exclusion_zones USING GIST (buffered_geometry)"
    )


def downgrade() -> None:
    # Drop spatial indexes
    op.execute("DROP INDEX IF EXISTS ix_exclusion_zones_buffered_geometry")
    op.execute("DROP INDEX IF EXISTS ix_exclusion_zones_geometry")

    # Drop regular indexes
    op.drop_index("ix_exclusion_zones_is_active", table_name="exclusion_zones")
    op.drop_index("ix_exclusion_zones_zone_type", table_name="exclusion_zones")
    op.drop_index("ix_exclusion_zones_user_id", table_name="exclusion_zones")
    op.drop_index("ix_exclusion_zones_project_id", table_name="exclusion_zones")

    # Drop table
    op.drop_table("exclusion_zones")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS zonesource")
    op.execute("DROP TYPE IF EXISTS zonetype")
