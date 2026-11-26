from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'idempotency_record',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('operation', sa.String(100), primary_key=True),
        sa.Column('idempotency_key', sa.String(128), primary_key=True),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp() + interval '24 hours'")),
        sa.CheckConstraint('(response_status IS NULL) = (response_body IS NULL)', name='ck_idempotency_response'),
    )
    op.create_index('ix_idempotency_expires_at', 'idempotency_record', ['expires_at'])


def downgrade():
    op.drop_table('idempotency_record')
