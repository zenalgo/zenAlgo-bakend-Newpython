"""merge_heads

Revision ID: 3ecf70092a23
Revises: c96b9843feb6, g1ff829b39d2
Create Date: 2026-09-01 12:03:37.357244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ecf70092a23'
down_revision: Union[str, Sequence[str], None] = ('c96b9843feb6', 'g1ff829b39d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
