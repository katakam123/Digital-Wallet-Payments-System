"""create digital wallet database tables

Revision ID: 1c5ac40e58e3
Revises: d5306982c09c
Create Date: 2026-11-04 00:58:12.036346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c5ac40e58e3'
down_revision: Union[str, Sequence[str], None] = 'd5306982c09c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
