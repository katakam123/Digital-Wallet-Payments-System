"""update ledger account balance constraint

Revision ID: 950a3781685a
Revises: 2ff976b462fe
Create Date: 2026-11-04 00:49:21.094817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '950a3781685a'
down_revision: Union[str, Sequence[str], None] = '2ff976b462fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
