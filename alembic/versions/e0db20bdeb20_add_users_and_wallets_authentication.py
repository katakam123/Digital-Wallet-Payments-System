"""add users and wallets authentication

Revision ID: e0db20bdeb20
Revises: d92fcbf6d2e1
Create Date: 2026-11-03 23:30:00.261101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0db20bdeb20'
down_revision: Union[str, Sequence[str], None] = 'd92fcbf6d2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
