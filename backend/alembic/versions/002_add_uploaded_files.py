"""Add uploaded_files table

Revision ID: 002
Revises: 001
Create Date: 2025-12-05

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums for file status and type
    op.execute(
        "CREATE TYPE filestatus AS ENUM ('pending', 'validating', 'valid', 'invalid', 'processing', 'processed', 'error');"
    )
    op.execute("CREATE TYPE filetype AS ENUM ('kmz', 'kml');")

    # Create uploaded_files table
    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        # File metadata
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column(
            "file_type",
            postgresql.ENUM("kmz", "kml", name="filetype", create_type=False),
            nullable=False,
        ),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        # Processing status
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "validating",
                "valid",
                "invalid",
                "processing",
                "processed",
                "error",
                name="filestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("validation_message", sa.Text(), nullable=True),
        # Geometry
        sa.Column(
            "boundary_geom",
            geoalchemy2.types.Geometry(
                geometry_type="GEOMETRY", srid=4326, spatial_index=True
            ),
            nullable=True,
        ),
        sa.Column("geometry_type", sa.String(length=50), nullable=True),
        sa.Column("feature_count", sa.Integer(), nullable=True),
        # Extracted metadata
        sa.Column("extracted_name", sa.String(length=255), nullable=True),
        sa.Column("extracted_description", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_uploaded_files_user_id", "uploaded_files", ["user_id"], unique=False
    )
    op.create_index(
        "ix_uploaded_files_project_id", "uploaded_files", ["project_id"], unique=False
    )
    op.create_index(
        "ix_uploaded_files_content_hash",
        "uploaded_files",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_uploaded_files_status", "uploaded_files", ["status"], unique=False
    )

    # Create spatial index
    op.execute(
        "CREATE INDEX idx_uploaded_files_boundary_geom ON uploaded_files USING GIST (boundary_geom);"
    )


def downgrade() -> None:
    op.drop_index("idx_uploaded_files_boundary_geom", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_status", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_content_hash", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_project_id", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_user_id", table_name="uploaded_files")
    op.drop_table("uploaded_files")
    op.execute("DROP TYPE filestatus;")
    op.execute("DROP TYPE filetype;")
