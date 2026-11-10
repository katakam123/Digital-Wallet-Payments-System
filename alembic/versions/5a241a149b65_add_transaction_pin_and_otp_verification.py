"""add transaction pin and otp verification

Revision ID: 5a241a149b65
Revises: 386aef9ac035
Create Date: 2026-11-04 00:22:48.347148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a241a149b65'
down_revision: Union[str, Sequence[str], None] = '386aef9ac035'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
