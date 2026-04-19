"""create_initial_schema

Revision ID: 7747b04a6ab1
Revises: 
Create Date: 2026-04-18 20:41:02.208787

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7747b04a6ab1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    marital_status_enum = postgresql.ENUM('single', 'married', 'divorced', 'widowed', name='maritalstatusenum')
    marital_status_enum.create(op.get_bind())
    
    income_range_enum = postgresql.ENUM('low', 'medium_low', 'medium', 'medium_high', 'high', name='incomerangeenum')
    income_range_enum.create(op.get_bind())
    
    risk_preference_enum = postgresql.ENUM('conservative', 'balanced', 'aggressive', name='riskpreferenceenum')
    risk_preference_enum.create(op.get_bind())
    
    health_status_enum = postgresql.ENUM('excellent', 'good', 'fair', 'poor', name='healthstatusenum')
    health_status_enum.create(op.get_bind())
    
    session_status_enum = postgresql.ENUM('active', 'background', 'completed', 'abandoned', 'archived', name='sessionstatusenum')
    session_status_enum.create(op.get_bind())
    
    message_role_enum = postgresql.ENUM('user', 'assistant', 'system', name='messageroleenum')
    message_role_enum.create(op.get_bind())
    
    check_result_enum = postgresql.ENUM('passed', 'failed', 'warning', 'manual_review', name='checkresultenum')
    check_result_enum.create(op.get_bind())
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(50), primary_key=True, comment='用户ID'),
        sa.Column('username', sa.String(100), nullable=True, comment='用户名'),
        sa.Column('email', sa.String(255), nullable=True, unique=True, comment='邮箱'),
        sa.Column('phone', sa.String(20), nullable=True, comment='手机号'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.Column('last_login_at', sa.DateTime(), nullable=True, comment='最后登录时间'),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_phone', 'users', ['phone'])
    
    # Create user_profiles table
    op.create_table(
        'user_profiles',
        sa.Column('profile_id', sa.String(50), primary_key=True, comment='画像ID'),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, comment='用户ID'),
        sa.Column('age', sa.Integer(), nullable=False, comment='年龄'),
        sa.Column('occupation', sa.String(100), nullable=False, comment='职业'),
        sa.Column('marital_status', marital_status_enum, nullable=False, comment='婚姻状况'),
        sa.Column('has_children', sa.Boolean(), nullable=False, server_default='false', comment='是否有子女'),
        sa.Column('children_count', sa.Integer(), nullable=False, server_default='0', comment='子女数量'),
        sa.Column('has_dependents', sa.Boolean(), nullable=False, server_default='false', comment='是否有被抚养人'),
        sa.Column('dependents_count', sa.Integer(), nullable=False, server_default='0', comment='被抚养人数量'),
        sa.Column('family_size', sa.Integer(), nullable=False, server_default='1', comment='家庭人数'),
        sa.Column('income_range', income_range_enum, nullable=False, comment='收入区间'),
        sa.Column('annual_income', sa.Float(), nullable=True, comment='年收入（具体金额）'),
        sa.Column('risk_preference', risk_preference_enum, nullable=True, comment='风险偏好'),
        sa.Column('risk_score', sa.Float(), nullable=True, comment='风险评分'),
        sa.Column('health_status', health_status_enum, nullable=True, comment='健康状况'),
        sa.Column('has_medical_history', sa.Boolean(), nullable=False, server_default='false', comment='是否有病史'),
        sa.Column('medical_conditions', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='已有疾病'),
        sa.Column('city', sa.String(50), nullable=True, comment='所在城市'),
        sa.Column('province', sa.String(50), nullable=True, comment='所在省份'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
    )
    op.create_index('idx_user_profiles_user_id', 'user_profiles', ['user_id'])
    op.create_index('idx_user_profiles_age', 'user_profiles', ['age'])
    op.create_index('idx_user_profiles_income_range', 'user_profiles', ['income_range'])
    
    # Create existing_coverage table
    op.create_table(
        'existing_coverage',
        sa.Column('coverage_id', sa.String(50), primary_key=True, comment='保障ID'),
        sa.Column('profile_id', sa.String(50), sa.ForeignKey('user_profiles.profile_id', ondelete='CASCADE'), nullable=False, comment='画像ID'),
        sa.Column('product_id', sa.String(50), nullable=False, comment='产品ID'),
        sa.Column('product_name', sa.String(200), nullable=False, comment='产品名称'),
        sa.Column('product_type', sa.String(50), nullable=False, comment='产品类型'),
        sa.Column('coverage_amount', sa.Float(), nullable=False, comment='保额'),
        sa.Column('premium', sa.Float(), nullable=False, comment='保费'),
        sa.Column('coverage_scope', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='保障范围'),
        sa.Column('purchase_date', sa.DateTime(), nullable=True, comment='购买日期'),
        sa.Column('coverage_start_date', sa.DateTime(), nullable=True, comment='保障开始日期'),
        sa.Column('coverage_end_date', sa.DateTime(), nullable=True, comment='保障结束日期'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='是否有效'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
    )
    op.create_index('idx_existing_coverage_profile_id', 'existing_coverage', ['profile_id'])
    op.create_index('idx_existing_coverage_product_type', 'existing_coverage', ['product_type'])
    op.create_index('idx_existing_coverage_is_active', 'existing_coverage', ['is_active'])
    
    # Create conversation_sessions table
    op.create_table(
        'conversation_sessions',
        sa.Column('session_id', sa.String(50), primary_key=True, comment='会话ID'),
        sa.Column('user_id', sa.String(50), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, comment='用户ID'),
        sa.Column('status', session_status_enum, nullable=False, server_default='active', comment='会话状态'),
        sa.Column('background_mode', sa.Boolean(), nullable=False, server_default='false', comment='是否后台运行'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('last_activity_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='最后活跃时间'),
        sa.Column('completed_at', sa.DateTime(), nullable=True, comment='完成时间'),
        sa.Column('turn_count', sa.Integer(), nullable=False, server_default='0', comment='对话轮数'),
        sa.Column('total_messages', sa.Integer(), nullable=False, server_default='0', comment='总消息数'),
        sa.Column('slots', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}', comment='槽位数据'),
        sa.Column('user_preferences', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='用户偏好'),
    )
    op.create_index('idx_conversation_sessions_user_id', 'conversation_sessions', ['user_id'])
    op.create_index('idx_conversation_sessions_status', 'conversation_sessions', ['status'])
    op.create_index('idx_conversation_sessions_created_at', 'conversation_sessions', ['created_at'])
    op.create_index('idx_conversation_sessions_last_activity', 'conversation_sessions', ['last_activity_at'])
    
    # Create conversation_messages table
    op.create_table(
        'conversation_messages',
        sa.Column('message_id', sa.String(50), primary_key=True, comment='消息ID'),
        sa.Column('session_id', sa.String(50), sa.ForeignKey('conversation_sessions.session_id', ondelete='CASCADE'), nullable=False, comment='会话ID'),
        sa.Column('role', message_role_enum, nullable=False, comment='消息角色'),
        sa.Column('content', sa.Text(), nullable=False, comment='消息内容'),
        sa.Column('intent', sa.String(50), nullable=True, comment='用户意图'),
        sa.Column('extracted_slots', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='提取的槽位'),
        sa.Column('agent_name', sa.String(50), nullable=True, comment='生成消息的Agent名称'),
        sa.Column('thinking_process', sa.Text(), nullable=True, comment='思考过程'),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='时间戳'),
    )
    op.create_index('idx_conversation_messages_session_id', 'conversation_messages', ['session_id'])
    op.create_index('idx_conversation_messages_timestamp', 'conversation_messages', ['timestamp'])
    op.create_index('idx_conversation_messages_role', 'conversation_messages', ['role'])
    
    # Create insurance_products table
    op.create_table(
        'insurance_products',
        sa.Column('product_id', sa.String(50), primary_key=True, comment='产品ID'),
        sa.Column('product_name', sa.String(200), nullable=False, comment='产品名称'),
        sa.Column('product_type', sa.String(50), nullable=False, comment='产品类型'),
        sa.Column('provider', sa.String(100), nullable=False, comment='保险公司'),
        sa.Column('coverage_scope', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='保障范围'),
        sa.Column('coverage_amount_min', sa.Float(), nullable=True, comment='最小保额'),
        sa.Column('coverage_amount_max', sa.Float(), nullable=True, comment='最大保额'),
        sa.Column('exclusions', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='责任免除'),
        sa.Column('premium_min', sa.Float(), nullable=False, comment='最低保费'),
        sa.Column('premium_max', sa.Float(), nullable=False, comment='最高保费'),
        sa.Column('payment_period', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='缴费期限选项'),
        sa.Column('coverage_period', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='保障期限选项'),
        sa.Column('age_min', sa.Integer(), nullable=False, comment='最小投保年龄'),
        sa.Column('age_max', sa.Integer(), nullable=False, comment='最大投保年龄'),
        sa.Column('occupation_restrictions', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='职业限制'),
        sa.Column('health_requirements', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='健康要求'),
        sa.Column('region_restrictions', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='地域限制'),
        sa.Column('features', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='产品特点'),
        sa.Column('advantages', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='产品优势'),
        sa.Column('suitable_for', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='适用人群'),
        sa.Column('claim_process', sa.Text(), nullable=True, comment='理赔流程'),
        sa.Column('waiting_period_days', sa.Integer(), nullable=False, server_default='0', comment='等待期（天）'),
        sa.Column('deductible', sa.Float(), nullable=False, server_default='0', comment='免赔额'),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true', comment='是否可售'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false', comment='是否推荐产品'),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True, comment='产品特征向量'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1', comment='版本号'),
    )
    op.create_index('idx_insurance_products_product_type', 'insurance_products', ['product_type'])
    op.create_index('idx_insurance_products_provider', 'insurance_products', ['provider'])
    op.create_index('idx_insurance_products_is_available', 'insurance_products', ['is_available'])
    op.create_index('idx_insurance_products_age_range', 'insurance_products', ['age_min', 'age_max'])
    op.create_index('idx_insurance_products_premium_range', 'insurance_products', ['premium_min', 'premium_max'])
    
    # Create recommendations table
    op.create_table(
        'recommendations',
        sa.Column('recommendation_id', sa.String(50), primary_key=True, comment='推荐ID'),
        sa.Column('session_id', sa.String(50), sa.ForeignKey('conversation_sessions.session_id', ondelete='CASCADE'), nullable=False, comment='会话ID'),
        sa.Column('product_id', sa.String(50), sa.ForeignKey('insurance_products.product_id', ondelete='CASCADE'), nullable=False, comment='产品ID'),
        sa.Column('rank', sa.Integer(), nullable=False, comment='推荐排名'),
        sa.Column('match_score', sa.Float(), nullable=False, comment='匹配分数'),
        sa.Column('confidence_score', sa.Float(), nullable=False, comment='推荐置信度'),
        sa.Column('explanation', sa.Text(), nullable=False, comment='推荐理由'),
        sa.Column('match_dimensions', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}', comment='各维度匹配分数'),
        sa.Column('why_suitable', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='为什么适合用户'),
        sa.Column('key_benefits', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='关键收益'),
        sa.Column('compliance_passed', sa.Boolean(), nullable=False, server_default='false', comment='是否通过合规检查'),
        sa.Column('compliance_issues', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='合规问题'),
        sa.Column('recommended_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='推荐时间'),
    )
    op.create_index('idx_recommendations_session_id', 'recommendations', ['session_id'])
    op.create_index('idx_recommendations_product_id', 'recommendations', ['product_id'])
    op.create_index('idx_recommendations_recommended_at', 'recommendations', ['recommended_at'])
    op.create_index('idx_recommendations_match_score', 'recommendations', ['match_score'])
    
    # Create user_feedback table
    op.create_table(
        'user_feedback',
        sa.Column('feedback_id', sa.String(50), primary_key=True, comment='反馈ID'),
        sa.Column('recommendation_id', sa.String(50), sa.ForeignKey('recommendations.recommendation_id', ondelete='CASCADE'), nullable=False, comment='推荐ID'),
        sa.Column('satisfaction', sa.String(20), nullable=False, comment='满意度（positive/negative/neutral）'),
        sa.Column('reason', sa.Text(), nullable=True, comment='反馈原因'),
        sa.Column('rating', sa.Integer(), nullable=True, comment='评分（1-5）'),
        sa.Column('helpful', sa.Boolean(), nullable=True, comment='是否有帮助'),
        sa.Column('meets_needs', sa.Boolean(), nullable=True, comment='是否符合需求'),
        sa.Column('comments', sa.Text(), nullable=True, comment='其他评论'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
    )
    op.create_index('idx_user_feedback_recommendation_id', 'user_feedback', ['recommendation_id'])
    op.create_index('idx_user_feedback_satisfaction', 'user_feedback', ['satisfaction'])
    op.create_index('idx_user_feedback_created_at', 'user_feedback', ['created_at'])
    
    # Create compliance_logs table
    op.create_table(
        'compliance_logs',
        sa.Column('log_id', sa.String(50), primary_key=True, comment='日志ID'),
        sa.Column('session_id', sa.String(50), nullable=False, comment='会话ID'),
        sa.Column('product_id', sa.String(50), nullable=False, comment='产品ID'),
        sa.Column('user_id', sa.String(50), nullable=False, comment='用户ID'),
        sa.Column('check_type', sa.String(50), nullable=False, comment='检查类型'),
        sa.Column('check_result', check_result_enum, nullable=False, comment='检查结果'),
        sa.Column('eligible', sa.Boolean(), nullable=False, comment='是否符合投保条件'),
        sa.Column('check_description', sa.Text(), nullable=False, comment='检查描述'),
        sa.Column('reason', sa.Text(), nullable=True, comment='未通过原因'),
        sa.Column('checked_value', sa.String(200), nullable=True, comment='被检查的值'),
        sa.Column('expected_value', sa.String(200), nullable=True, comment='期望的值'),
        sa.Column('checks_detail', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]', comment='详细检查列表'),
        sa.Column('failed_checks', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='未通过的检查'),
        sa.Column('recommendations', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='改进建议'),
        sa.Column('checked_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='检查时间'),
    )
    op.create_index('idx_compliance_logs_session_id', 'compliance_logs', ['session_id'])
    op.create_index('idx_compliance_logs_product_id', 'compliance_logs', ['product_id'])
    op.create_index('idx_compliance_logs_user_id', 'compliance_logs', ['user_id'])
    op.create_index('idx_compliance_logs_check_result', 'compliance_logs', ['check_result'])
    op.create_index('idx_compliance_logs_checked_at', 'compliance_logs', ['checked_at'])
    
    # Create quality_metrics table
    op.create_table(
        'quality_metrics',
        sa.Column('metric_id', sa.String(50), primary_key=True, comment='指标ID'),
        sa.Column('session_id', sa.String(50), nullable=False, comment='会话ID'),
        sa.Column('intent_recognition_accuracy', sa.Float(), nullable=True, comment='意图识别准确率'),
        sa.Column('slot_fill_rate', sa.Float(), nullable=True, comment='槽位填充率'),
        sa.Column('conversation_completion_rate', sa.Float(), nullable=True, comment='对话完成率'),
        sa.Column('recommendation_confidence', sa.Float(), nullable=True, comment='推荐置信度'),
        sa.Column('recommendation_diversity', sa.Float(), nullable=True, comment='推荐多样性'),
        sa.Column('compliance_pass_rate', sa.Float(), nullable=True, comment='合规通过率'),
        sa.Column('total_turns', sa.Integer(), nullable=False, comment='总对话轮数'),
        sa.Column('total_tokens', sa.Integer(), nullable=True, comment='总Token数'),
        sa.Column('response_time_ms', sa.Integer(), nullable=True, comment='响应时间（毫秒）'),
        sa.Column('user_satisfaction', sa.String(20), nullable=True, comment='用户满意度'),
        sa.Column('quality_score', sa.Float(), nullable=True, comment='质量评分'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
    )
    op.create_index('idx_quality_metrics_session_id', 'quality_metrics', ['session_id'])
    op.create_index('idx_quality_metrics_created_at', 'quality_metrics', ['created_at'])
    op.create_index('idx_quality_metrics_quality_score', 'quality_metrics', ['quality_score'])
    
    # Create archived_sessions table
    op.create_table(
        'archived_sessions',
        sa.Column('archive_id', sa.String(50), primary_key=True, comment='归档ID'),
        sa.Column('session_id', sa.String(50), nullable=False, comment='原会话ID'),
        sa.Column('user_id', sa.String(50), nullable=False, comment='用户ID'),
        sa.Column('session_summary', sa.Text(), nullable=True, comment='会话摘要'),
        sa.Column('key_intents', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='关键意图'),
        sa.Column('extracted_profile', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='提取的用户画像'),
        sa.Column('recommended_products', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}', comment='推荐的产品ID列表'),
        sa.Column('user_feedback_summary', sa.Text(), nullable=True, comment='用户反馈摘要'),
        sa.Column('full_conversation', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='完整对话数据'),
        sa.Column('final_state', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='最终状态'),
        sa.Column('session_embedding', postgresql.ARRAY(sa.Float()), nullable=True, comment='会话特征向量'),
        sa.Column('session_created_at', sa.DateTime(), nullable=False, comment='会话创建时间'),
        sa.Column('session_completed_at', sa.DateTime(), nullable=False, comment='会话完成时间'),
        sa.Column('archived_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='归档时间'),
    )
    op.create_index('idx_archived_sessions_session_id', 'archived_sessions', ['session_id'])
    op.create_index('idx_archived_sessions_user_id', 'archived_sessions', ['user_id'])
    op.create_index('idx_archived_sessions_archived_at', 'archived_sessions', ['archived_at'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('archived_sessions')
    op.drop_table('quality_metrics')
    op.drop_table('compliance_logs')
    op.drop_table('user_feedback')
    op.drop_table('recommendations')
    op.drop_table('insurance_products')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_sessions')
    op.drop_table('existing_coverage')
    op.drop_table('user_profiles')
    op.drop_table('users')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS checkresultenum')
    op.execute('DROP TYPE IF EXISTS messageroleenum')
    op.execute('DROP TYPE IF EXISTS sessionstatusenum')
    op.execute('DROP TYPE IF EXISTS healthstatusenum')
    op.execute('DROP TYPE IF EXISTS riskpreferenceenum')
    op.execute('DROP TYPE IF EXISTS incomerangeenum')
    op.execute('DROP TYPE IF EXISTS maritalstatusenum')
