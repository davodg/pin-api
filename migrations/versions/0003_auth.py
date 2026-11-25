from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_user',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("role IN ('viewer', 'admin')", name='ck_app_user_role'),
    )
    op.create_table(
        'login_attempt',
        sa.Column('address', sa.String(255), primary_key=True),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
    )
    op.create_index('ix_login_attempt_window_start', 'login_attempt', ['window_start'])


def downgrade():
    op.drop_table('login_attempt')
    op.drop_table('app_user')
