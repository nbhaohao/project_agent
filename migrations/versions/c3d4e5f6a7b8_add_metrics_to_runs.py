"""add metrics to runs

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('input_tokens', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('output_tokens', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True))
    op.add_column('runs', sa.Column('llm_calls', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('runs', 'llm_calls')
    op.drop_column('runs', 'cost_usd')
    op.drop_column('runs', 'output_tokens')
    op.drop_column('runs', 'input_tokens')
