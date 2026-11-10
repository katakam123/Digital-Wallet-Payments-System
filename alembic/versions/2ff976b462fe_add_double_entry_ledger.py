"""add double entry ledger

Revision ID: 2ff976b462fe
Revises: 5a241a149b65
Create Date: 2026-11-04 00:40:02.048356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ff976b462fe'
down_revision: Union[str, Sequence[str], None] = '5a241a149b65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
