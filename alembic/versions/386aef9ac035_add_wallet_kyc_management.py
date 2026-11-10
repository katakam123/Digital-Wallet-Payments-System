"""add wallet kyc management

Revision ID: 386aef9ac035
Revises: e0db20bdeb20
Create Date: 2026-11-04 00:03:52.924813

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '386aef9ac035'
down_revision: Union[str, Sequence[str], None] = 'e0db20bdeb20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
