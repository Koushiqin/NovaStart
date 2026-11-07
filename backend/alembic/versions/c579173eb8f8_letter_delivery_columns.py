"""letter delivery columns

Revision ID: c579173eb8f8
Revises: 2cfedebff490
Create Date: 2026-11-07 21:18:16.067087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c579173eb8f8'
down_revision: Union[str, Sequence[str], None] = '2cfedebff490'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: letters 增加发件人、送达状态、专注时投递标签。"""
    op.add_column('letters', sa.Column('sender_id', sa.Integer(), nullable=True))
    op.add_column('letters', sa.Column('status', sa.String(length=20), server_default=sa.text("'delivered'"), nullable=False))
    op.add_column('letters', sa.Column('focused_delivery', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_index(op.f('ix_letters_sender_id'), 'letters', ['sender_id'], unique=False)
    op.create_foreign_key(
        'fk_letters_sender_id_users', 'letters', 'users', ['sender_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_letters_sender_id_users', 'letters', type_='foreignkey')
    op.drop_index(op.f('ix_letters_sender_id'), table_name='letters')
    op.drop_column('letters', 'focused_delivery')
    op.drop_column('letters', 'status')
    op.drop_column('letters', 'sender_id')
