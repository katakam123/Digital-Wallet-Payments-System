"""create ledger tables

Revision ID: d5306982c09c
Revises: 950a3781685a
Create Date: 2026-11-04 00:55:34.716189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5306982c09c'
down_revision: Union[str, Sequence[str], None] = '950a3781685a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
