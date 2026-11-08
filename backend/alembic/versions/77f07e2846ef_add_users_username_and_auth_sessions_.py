"""add users.username and auth_sessions table

Revision ID: 77f07e2846ef
Revises: 6c2337279336
Create Date: 2026-11-08 13:03:59.673825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77f07e2846ef'
down_revision: Union[str, Sequence[str], None] = '6c2337279336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('auth_sessions',
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('token')
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)

    # 1) 先以可空加列，避免存量行无值导致 not null 约束失败
    op.add_column('users', sa.Column('username', sa.String(length=15), nullable=True))

    # 2) 回填存量演示账号的 username；其他存量账号用 id 兜底，保证非空
    op.execute(
        "UPDATE users SET username = CASE name "
        "WHEN '小明' THEN 'xiaoming' "
        "WHEN '小美' THEN 'xiaomei' "
        "WHEN '小刚' THEN 'xiaogang' "
        "ELSE 'user_' || id END "
        "WHERE username IS NULL"
    )

    # 3) 回填完成后置为非空
    op.alter_column('users', 'username',
                    existing_type=sa.String(length=15),
                    nullable=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_column('users', 'username')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
