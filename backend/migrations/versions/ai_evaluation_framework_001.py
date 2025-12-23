# -*- coding: utf-8 -*-
"""AI Evaluation Framework database migration

Revision ID: ai_evaluation_framework_001
Revises: 
Create Date: 2024-01-01 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ai_evaluation_framework_001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Create AI Evaluation Framework tables."""
    
    # Create enum types
    evaluation_type = postgresql.ENUM(
        'llm_as_judge', 'regression_test', 'determinism_test', 
        'performance_benchmark', 'security_audit', 'best_practices', 
        'functionality_test', 'readability_eval',
        name='evaluation_type_enum'
    )
    
    evaluation_status = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed', 'cancelled', 
        'timeout', 'error', 'skipped',
        name='evaluation_status_enum'
    )
    
    complexity_level = postgresql.ENUM(
        'easy', 'medium', 'hard', 'expert',
        name='complexity_level_enum'
    )
    
    regression_alert_type = postgresql.ENUM(
        'score_degradation', 'consistency_drop', 'failure_rate_increase',
        'cost_spike', 'pattern_change', 'performance_degradation',
        'security_regression', 'functionality_break',
        name='regression_alert_type_enum'
    )
    
    evaluation_type.create(op.get_bind())
    evaluation_status.create(op.get_bind())
    complexity_level.create(op.get_bind())
    regression_alert_type.create(op.get_bind())
    
    # Create evaluation_scenarios table
    op.create_table('evaluation_scenarios',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('complexity_level', complexity_level, nullable=False),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('framework', sa.String(length=100), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('expected_output', sa.Text(), nullable=True),
        sa.Column('evaluation_criteria', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_scenarios_id'), 'evaluation_scenarios', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_scenarios_name'), 'evaluation_scenarios', ['name'], unique=False)
    op.create_index(op.f('ix_evaluation_scenarios_category'), 'evaluation_scenarios', ['category'], unique=False)
    op.create_index(op.f('ix_evaluation_scenarios_complexity_level'), 'evaluation_scenarios', ['complexity_level'], unique=False)
    
    # Create evaluation_results table
    op.create_table('evaluation_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scenario_id', sa.String(length=36), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=True),
        sa.Column('task_run_id', sa.String(length=36), nullable=True),
        sa.Column('commit_hash', sa.String(length=40), nullable=True),
        sa.Column('branch_name', sa.String(length=255), nullable=True),
        sa.Column('evaluation_type', evaluation_type, nullable=False),
        sa.Column('status', evaluation_status, nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('judge_model', sa.String(length=100), nullable=False),
        sa.Column('judge_provider', sa.String(length=50), nullable=False),
        sa.Column('judge_version', sa.String(length=50), nullable=True),
        sa.Column('judge_temperature', sa.Float(), nullable=False),
        sa.Column('code_safety_score', sa.Float(), nullable=True),
        sa.Column('code_quality_score', sa.Float(), nullable=True),
        sa.Column('best_practices_score', sa.Float(), nullable=True),
        sa.Column('performance_score', sa.Float(), nullable=True),
        sa.Column('readability_score', sa.Float(), nullable=True),
        sa.Column('functionality_score', sa.Float(), nullable=True),
        sa.Column('security_score', sa.Float(), nullable=True),
        sa.Column('maintainability_score', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('weighted_score', sa.Float(), nullable=True),
        sa.Column('percentile_rank', sa.Float(), nullable=True),
        sa.Column('judge_feedback', sa.Text(), nullable=True),
        sa.Column('improvement_suggestions', sa.JSON(), nullable=True),
        sa.Column('code_violations', sa.JSON(), nullable=True),
        sa.Column('best_practices_mentioned', sa.JSON(), nullable=True),
        sa.Column('agent_output', sa.Text(), nullable=True),
        sa.Column('expected_output', sa.Text(), nullable=True),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('semantic_similarity', sa.Float(), nullable=True),
        sa.Column('judge_tokens_used', sa.Integer(), nullable=True),
        sa.Column('judge_cost_usd', sa.Float(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['evaluation_scenarios.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_results_id'), 'evaluation_results', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_results_scenario_id'), 'evaluation_results', ['scenario_id'], unique=False)
    op.create_index(op.f('ix_evaluation_results_task_id'), 'evaluation_results', ['task_id'], unique=False)
    op.create_index(op.f('ix_evaluation_results_task_run_id'), 'evaluation_results', ['task_run_id'], unique=False)
    op.create_index(op.f('ix_evaluation_results_commit_hash'), 'evaluation_results', ['commit_hash'], unique=False)
    op.create_index(op.f('ix_evaluation_results_branch_name'), 'evaluation_results', ['branch_name'], unique=False)
    op.create_index(op.f('ix_evaluation_results_evaluation_type'), 'evaluation_results', ['evaluation_type'], unique=False)
    op.create_index(op.f('ix_evaluation_results_status'), 'evaluation_results', ['status'], unique=False)
    op.create_index(op.f('ix_evaluation_results_overall_score'), 'evaluation_results', ['overall_score'], unique=False)
    op.create_index(op.f('ix_evaluation_results_completed_at'), 'evaluation_results', ['completed_at'], unique=False)
    
    # Composite indexes for performance
    op.create_index('idx_evaluation_scenario_status', 'evaluation_results', ['scenario_id', 'status'])
    op.create_index('idx_evaluation_commit_branch', 'evaluation_results', ['commit_hash', 'branch_name'])
    
    # Create regression_tests table
    op.create_table('regression_tests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scenario_id', sa.String(length=36), nullable=False),
        sa.Column('baseline_evaluation_id', sa.String(length=36), nullable=True),
        sa.Column('current_evaluation_id', sa.String(length=36), nullable=True),
        sa.Column('commit_hash', sa.String(length=40), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('trigger_type', sa.String(length=50), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=True),
        sa.Column('baseline_score', sa.Float(), nullable=True),
        sa.Column('current_score', sa.Float(), nullable=True),
        sa.Column('score_change', sa.Float(), nullable=True),
        sa.Column('score_change_percentage', sa.Float(), nullable=True),
        sa.Column('degradation_threshold_percentage', sa.Float(), nullable=False),
        sa.Column('alert_triggered', sa.Boolean(), nullable=False),
        sa.Column('alert_type', regression_alert_type, nullable=True),
        sa.Column('alert_message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_blocking', sa.Boolean(), nullable=False),
        sa.Column('detailed_analysis', sa.JSON(), nullable=True),
        sa.Column('recommendations', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['evaluation_scenarios.id'], ),
        sa.ForeignKeyConstraint(['baseline_evaluation_id'], ['evaluation_results.id'], ),
        sa.ForeignKeyConstraint(['current_evaluation_id'], ['evaluation_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regression_tests_id'), 'regression_tests', ['id'], unique=False)
    op.create_index(op.f('ix_regression_tests_scenario_id'), 'regression_tests', ['scenario_id'], unique=False)
    op.create_index(op.f('ix_regression_tests_commit_hash'), 'regression_tests', ['commit_hash'], unique=False)
    op.create_index(op.f('ix_regression_tests_branch_name'), 'regression_tests', ['branch_name'], unique=False)
    op.create_index(op.f('ix_regression_tests_status'), 'regression_tests', ['status'], unique=False)
    op.create_index(op.f('ix_regression_tests_alert_triggered'), 'regression_tests', ['alert_triggered'], unique=False)
    op.create_index(op.f('ix_regression_tests_score_change_percentage'), 'regression_tests', ['score_change_percentage'], unique=False)
    
    # Composite indexes
    op.create_index('idx_regression_commit_branch', 'regression_tests', ['commit_hash', 'branch_name'])
    
    # Create pass_k_metrics table
    op.create_table('pass_k_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scenario_id', sa.String(length=36), nullable=False),
        sa.Column('evaluation_result_id', sa.String(length=36), nullable=False),
        sa.Column('k_value', sa.Integer(), nullable=False),
        sa.Column('total_runs', sa.Integer(), nullable=False),
        sa.Column('successful_runs', sa.Integer(), nullable=False),
        sa.Column('pass_at_k', sa.Float(), nullable=False),
        sa.Column('confidence_interval_lower', sa.Float(), nullable=True),
        sa.Column('confidence_interval_upper', sa.Float(), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=False),
        sa.Column('success_threshold', sa.Float(), nullable=False),
        sa.Column('success_criteria', sa.JSON(), nullable=False),
        sa.Column('score_variance', sa.Float(), nullable=True),
        sa.Column('score_std_deviation', sa.Float(), nullable=True),
        sa.Column('score_range_min', sa.Float(), nullable=True),
        sa.Column('score_range_max', sa.Float(), nullable=True),
        sa.Column('failure_patterns', sa.JSON(), nullable=True),
        sa.Column('common_failures', sa.JSON(), nullable=True),
        sa.Column('error_categories', sa.JSON(), nullable=True),
        sa.Column('consistency_score', sa.Float(), nullable=True),
        sa.Column('reliability_grade', sa.String(length=10), nullable=True),
        sa.Column('run_timestamp', sa.DateTime(), nullable=False),
        sa.Column('run_duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['evaluation_scenarios.id'], ),
        sa.ForeignKeyConstraint(['evaluation_result_id'], ['evaluation_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pass_k_metrics_id'), 'pass_k_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_pass_k_metrics_scenario_id'), 'pass_k_metrics', ['scenario_id'], unique=False)
    op.create_index(op.f('ix_pass_k_metrics_evaluation_result_id'), 'pass_k_metrics', ['evaluation_result_id'], unique=False)
    op.create_index(op.f('ix_pass_k_metrics_k_value'), 'pass_k_metrics', ['k_value'], unique=False)
    op.create_index(op.f('ix_pass_k_metrics_pass_at_k'), 'pass_k_metrics', ['pass_at_k'], unique=False)
    op.create_index(op.f('ix_pass_k_metrics_reliability_grade'), 'pass_k_metrics', ['reliability_grade'], unique=False)
    op.create_index(op.f('ix_pass_k_metrics_run_timestamp'), 'pass_k_metrics', ['run_timestamp'], unique=False)
    
    # Composite indexes
    op.create_index('idx_pass_k_scenario_k', 'pass_k_metrics', ['scenario_id', 'k_value'])
    
    # Create regression_metrics table
    op.create_table('regression_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('evaluation_result_id', sa.String(length=36), nullable=False),
        sa.Column('historical_avg_score', sa.Float(), nullable=True),
        sa.Column('historical_std_deviation', sa.Float(), nullable=True),
        sa.Column('historical_median_score', sa.Float(), nullable=True),
        sa.Column('historical_percentile_25', sa.Float(), nullable=True),
        sa.Column('historical_percentile_75', sa.Float(), nullable=True),
        sa.Column('historical_percentile_90', sa.Float(), nullable=True),
        sa.Column('trend_direction', sa.String(length=20), nullable=True),
        sa.Column('trend_strength', sa.Float(), nullable=True),
        sa.Column('last_significant_change', sa.DateTime(), nullable=True),
        sa.Column('improvement_count', sa.Integer(), nullable=False),
        sa.Column('degradation_count', sa.Integer(), nullable=False),
        sa.Column('vs_best_score', sa.Float(), nullable=True),
        sa.Column('vs_worst_score', sa.Float(), nullable=True),
        sa.Column('vs_median_score', sa.Float(), nullable=True),
        sa.Column('quality_gate_threshold', sa.Float(), nullable=False),
        sa.Column('quality_gate_status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['evaluation_result_id'], ['evaluation_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regression_metrics_id'), 'regression_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_regression_metrics_evaluation_result_id'), 'regression_metrics', ['evaluation_result_id'], unique=False)
    
    # Create evaluation_dashboard table
    op.create_table('evaluation_dashboard',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dashboard_type', sa.String(length=50), nullable=False),
        sa.Column('time_range_days', sa.Integer(), nullable=False),
        sa.Column('scenarios_filter', sa.JSON(), nullable=True),
        sa.Column('metrics_to_display', sa.JSON(), nullable=False),
        sa.Column('cached_metrics', sa.JSON(), nullable=True),
        sa.Column('last_cache_update', sa.DateTime(), nullable=True),
        sa.Column('cache_ttl_minutes', sa.Integer(), nullable=False),
        sa.Column('alert_thresholds', sa.JSON(), nullable=True),
        sa.Column('notification_channels', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_dashboard_id'), 'evaluation_dashboard', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_dashboard_dashboard_type'), 'evaluation_dashboard', ['dashboard_type'], unique=False)
    op.create_index(op.f('ix_evaluation_dashboard_workspace_id'), 'evaluation_dashboard', ['workspace_id'], unique=False)
    
    # Create evaluation_alerts table
    op.create_table('evaluation_alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('alert_type', regression_alert_type, nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('scenario_id', sa.String(length=36), nullable=True),
        sa.Column('regression_test_id', sa.String(length=36), nullable=True),
        sa.Column('evaluation_result_id', sa.String(length=36), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=True),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('acknowledged_by', sa.String(length=100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('commit_hash', sa.String(length=40), nullable=True),
        sa.Column('branch_name', sa.String(length=255), nullable=True),
        sa.Column('triggered_by', sa.String(length=100), nullable=True),
        sa.Column('alert_metadata', sa.JSON(), nullable=True),  # Renamed from 'metadata' to avoid SQLAlchemy reserved name conflict
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['evaluation_scenarios.id'], ),
        sa.ForeignKeyConstraint(['regression_test_id'], ['regression_tests.id'], ),
        sa.ForeignKeyConstraint(['evaluation_result_id'], ['evaluation_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_alerts_id'), 'evaluation_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_alert_type'), 'evaluation_alerts', ['alert_type'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_severity'), 'evaluation_alerts', ['severity'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_scenario_id'), 'evaluation_alerts', ['scenario_id'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_regression_test_id'), 'evaluation_alerts', ['regression_test_id'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_evaluation_result_id'), 'evaluation_alerts', ['evaluation_result_id'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_status'), 'evaluation_alerts', ['status'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_commit_hash'), 'evaluation_alerts', ['commit_hash'], unique=False)
    op.create_index(op.f('ix_evaluation_alerts_created_at'), 'evaluation_alerts', ['created_at'], unique=False)


def downgrade():
    """Drop AI Evaluation Framework tables."""
    
    # Drop tables in reverse order to handle foreign key constraints
    op.drop_table('evaluation_alerts')
    op.drop_table('evaluation_dashboard')
    op.drop_table('regression_metrics')
    op.drop_table('pass_k_metrics')
    op.drop_table('regression_tests')
    op.drop_table('evaluation_results')
    op.drop_table('evaluation_scenarios')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS evaluation_type_enum')
    op.execute('DROP TYPE IF EXISTS evaluation_status_enum')
    op.execute('DROP TYPE IF EXISTS complexity_level_enum')
    op.execute('DROP TYPE IF EXISTS regression_alert_type_enum')