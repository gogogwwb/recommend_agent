"""add warm data layer fields

Revision ID: add_warm_data_layer
Revises: 7747b04a6ab1
Create Date: 2026-04-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_warm_data_layer'
down_revision = '7747b04a6ab1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add warm data layer fields to conversation_sessions table
    
    New fields:
    - warm_messages: JSONB array storing uncompressed warm messages
    - compressed_history: TEXT storing compressed conversation history
    - compression_count: INT tracking number of compression batches
    """
    # Add warm_messages column (JSONB array)
    op.add_column(
        'conversation_sessions',
        sa.Column(
            'warm_messages',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='[]',
            comment='温数据层未压缩消息'
        )
    )
    
    # Add compressed_history column (TEXT)
    op.add_column(
        'conversation_sessions',
        sa.Column(
            'compressed_history',
            sa.Text(),
            nullable=False,
            server_default='',
            comment='压缩的历史对话摘要'
        )
    )
    
    # Add compression_count column (INT)
    op.add_column(
        'conversation_sessions',
        sa.Column(
            'compression_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='压缩批次计数'
        )
    )
    
    # Create index on compression_count for monitoring
    op.create_index(
        'idx_sessions_compression_count',
        'conversation_sessions',
        ['compression_count']
    )


def downgrade() -> None:
    """
    Remove warm data layer fields from conversation_sessions table
    """
    # Drop index
    op.drop_index('idx_sessions_compression_count', table_name='conversation_sessions')
    
    # Drop columns
    op.drop_column('conversation_sessions', 'compression_count')
    op.drop_column('conversation_sessions', 'compressed_history')
    op.drop_column('conversation_sessions', 'warm_messages')
