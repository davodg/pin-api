from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():

    op.create_table(
        'employee_feedback',
        sa.Column('id', sa.String(36), primary_key=True, server_default=sa.text("uuid_generate_v4()")),

        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('corporate_email', sa.String(255), nullable=False),
        sa.Column('phone_number', sa.String(50), nullable=True),
        sa.Column('department', sa.String(255), nullable=False),
        sa.Column('location', sa.String(255), nullable=False),
        sa.Column('company_tenure', sa.String(100), nullable=False),
        sa.Column('gender', sa.String(50), nullable=False),
        sa.Column('generation', sa.String(50), nullable=False),

        sa.Column('l0_company', sa.String(255), nullable=True),
        sa.Column('l1_directorate', sa.String(255), nullable=True),
        sa.Column('l2_management', sa.String(255), nullable=True),
        sa.Column('l3_coordination', sa.String(255), nullable=True),
        sa.Column('l4_area', sa.String(255), nullable=True),

        sa.Column('response_date', sa.DateTime(), nullable=True),

        sa.Column('interest_in_position', sa.Integer(), nullable=False),
        sa.Column('interest_in_position_comments', sa.Text(), nullable=True),

        sa.Column('contribution', sa.Integer(), nullable=False),
        sa.Column('contribution_comments', sa.Text(), nullable=True),

        sa.Column('learning_and_development', sa.Integer(), nullable=False),
        sa.Column('learning_and_development_comments', sa.Text(), nullable=True),

        sa.Column('feedback', sa.Integer(), nullable=False),
        sa.Column('feedback_comments', sa.Text(), nullable=True),

        sa.Column('manager_interaction', sa.Integer(), nullable=False),
        sa.Column('manager_interaction_comments', sa.Text(), nullable=True),

        sa.Column('opportunity_clarity', sa.Integer(), nullable=False),
        sa.Column('opportunity_clarity_comments', sa.Text(), nullable=True),

        sa.Column('permanence_expectation', sa.Integer(), nullable=False),
        sa.Column('permanence_expectation_comments', sa.Text(), nullable=True),

        sa.Column('enps', sa.Integer(), nullable=False),
        sa.Column('enps_comments', sa.Text(), nullable=True),
    )

    op.create_index('idx_employee_feedback_email', 'employee_feedback', ['email'])
    op.create_index('idx_employee_feedback_corporate_email', 'employee_feedback', ['corporate_email'])
    op.create_index('idx_employee_feedback_response_date', 'employee_feedback', ['response_date'])
    op.create_index('idx_employee_feedback_name', 'employee_feedback', ['name'])
    op.create_index('idx_employee_feedback_department', 'employee_feedback', ['department'])
    op.create_index('idx_employee_feedback_location', 'employee_feedback', ['location'])
    op.create_index('idx_employee_feedback_gender', 'employee_feedback', ['gender'])
    op.create_index('idx_employee_feedback_generation', 'employee_feedback', ['generation'])


def downgrade():
    op.drop_index('idx_employee_feedback_generation', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_gender', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_location', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_department', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_name', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_response_date', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_corporate_email', table_name='employee_feedback')
    op.drop_index('idx_employee_feedback_email', table_name='employee_feedback')

    op.drop_table('employee_feedback')

