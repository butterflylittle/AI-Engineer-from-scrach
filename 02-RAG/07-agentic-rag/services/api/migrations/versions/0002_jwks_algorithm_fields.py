"""Add Better Auth 1.7 JWKS algorithm metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0002_jwks_algorithm_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jwks", sa.Column("alg", sa.Text(), nullable=True))
    op.add_column("jwks", sa.Column("crv", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jwks", "crv")
    op.drop_column("jwks", "alg")
