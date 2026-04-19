# Implementation Plan: 保险智能推荐Agent系统

## Overview

本实现计划基于LangGraph 1.0.0多Agent架构，实现一个智能保险推荐对话系统。系统采用主子图架构（Main Graph + 3个专门化Subgraph），使用PostgresSaver管理会话状态，使用Store API管理用户画像，通过FastAPI + SSE提供实时流式响应。

**技术栈**: Python 3.11+, LangGraph 1.0.0, LangChain 1.0.0, FAISS, PostgreSQL, FastAPI, uv

**核心特性**:
- 子图架构（Profile Subgraph、Recommendation Subgraph、Compliance Subgraph）
- PostgresSaver集成（会话状态持久化和恢复）
- Store API集成（跨会话持久化用户画像和关键槽位）
- Skills + MCP集成（4个Skills + 4个MCP服务器）
- 会话管理（多会话隔离、切换、后台运行）
- 性能优化（流式响应）

**架构变更**:
- ✅ 使用子图Schema替代Context Isolation（结构化隔离，无需运行时过滤）
- ✅ 使用PostgresSaver替代HotDataLayer/WarmDataLayer（原生会话管理）
- ✅ 引入Store API管理用户画像（跨会话持久化）

## Tasks

- [x] 1. 项目初始化和环境配置
  - 使用uv创建Python项目结构
  - 配置pyproject.toml，添加核心依赖（langgraph==1.0.0, langchain==1.0.0, fastapi, pydantic, psycopg2, faiss-cpu, hypothesis）
  - 创建目录结构（agents/, skills/, tools/, api/, models/, utils/, tests/）
  - 配置环境变量模板（.env.example）
  - 设置日志配置（logging.yaml）
  - _Requirements: 项目基础设施_

- [ ] 2. 数据库设计和初始化
  - [x] 2.1 创建PostgreSQL数据库Schema
    - 创建users、user_profiles、conversation_sessions、conversation_messages表
    - 创建insurance_products、existing_coverage、recommendations表
    - 创建user_feedback、compliance_logs、quality_metrics、archived_sessions表
    - 添加索引和外键约束
    - _Requirements: 6.1, 12.1, 14.1_
  
  - [x] 2.2 实现数据库迁移脚本
    - 使用Alembic创建迁移管理
    - 编写初始化迁移脚本
    - 编写种子数据脚本（测试用保险产品数据）
    - _Requirements: 6.1_
  
  - [x] 2.3 初始化FAISS向量索引
    - 创建FAISS IndexFlatIP索引（dimension=768）
    - 实现索引持久化和加载逻辑
    - 创建product_id到vector_id的映射表
    - _Requirements: 6.4, 7.1_

- [ ] 3. 核心数据模型实现
  - [x] 3.1 定义Pydantic数据模型
    - 实现UserProfile、RiskPreference、ExistingProduct模型
    - 实现Product、RecommendationResult、Message模型
    - 实现CoverageGap、ComplianceCheck、DisclosureInfo模型
    - 实现AgentState（LangGraph状态模型）
    - _Requirements: 1.3, 2.2, 6.1, 7.3_
  
  - [x] 3.2 定义子图State模型（LangGraph 1.0.0）
    - 创建models/subgraph_states.py
    - 实现ProfileState（messages, user_id, session_id, user_profile, slots）
    - 实现RecommendationState（user_id, session_id, user_profile, recommendations, explanations）
    - 实现ComplianceState（user_id, session_id, user_profile, recommendations, compliance_checks, disclosure_info）
    - 实现MainState（messages, user_id, session_id, user_profile, recommendations, compliance_checks）
    - _Requirements: 子图架构_
  
  - [ ]* 3.3 编写数据模型属性测试
    - **Property 1: 用户画像序列化往返一致性**
    - **Validates: Requirements 1.5**
    - 使用Hypothesis生成随机UserProfile，验证JSON序列化往返一致性
  
  - [ ]* 3.4 编写数据模型属性测试
    - **Property 2: 产品数据序列化往返一致性**
    - **Validates: Requirements 6.5**
    - 使用Hypothesis生成随机Product，验证数据库存储往返一致性
  
  - [x] 3.5 实现SQLAlchemy ORM模型
    - 创建与PostgreSQL表对应的ORM模型
    - 实现模型与Pydantic模型的转换方法
    - _Requirements: 6.1_

- [ ] 4. PostgresSaver和Store API集成（LangGraph 1.0.0）
  - [x] 4.1 实现PostgresSaver配置
    - 创建utils/checkpointer.py
    - 使用PostgresSaver初始化Checkpointer（from_conn_string）
    - 运行checkpointer.setup()创建必要的表结构
    - 实现get_checkpointer工厂方法
    - _Requirements: 会话状态管理_
  
  - [x] 4.2 实现StoreManager
    - 创建utils/store_manager.py
    - 使用PostgresStore初始化Store（from_conn_string）
    - 实现put_user_profile方法（存储用户画像到namespace=("users", user_id)）
    - 实现get_user_profile方法（从Store读取用户画像）
    - 实现update_user_profile方法（合并更新用户画像）
    - 实现put_session_metadata方法（存储会话元数据）
    - _Requirements: Store API集成_
  
  - [x] 4.3 配置Store数据库表
    - 运行store.setup()创建Store所需表结构
    - 验证Store表与现有数据库兼容
    - 创建setup_store.py脚本用于Store表初始化和验证
    - 编写test_store_setup.py单元测试验证Store设置逻辑
    - 更新docs/database_setup.md文档添加Store表说明
    - _Requirements: Store API集成_
  
  - [ ]* 4.4 编写Store API属性测试
    - **Property 3: 用户画像持久化往返一致性**
    - **Validates: Store API集成**
    - 验证用户画像存储到Store后再读取，产生等价的画像数据

- [ ] 5. Checkpoint - 确保数据层测试通过
  - 运行所有数据模型和记忆系统的单元测试
  - 验证PostgreSQL、FAISS连接正常
  - 验证PostgresSaver和Store API读写正常
  - 确认数据序列化往返一致性
  - 如有问题，询问用户

- [ ] 6. 子图架构实现（LangGraph 1.0.0）
  - [ ] 6.1 实现Profile Subgraph
    - 创建agents/profile_subgraph.py
    - 实现extract_slots_node（从对话中提取槽位）
    - 实现validate_profile_node（验证画像完整性）
    - 实现槽位存储到Store API（store.put）
    - 构建ProfileState子图（StateGraph + START + END）
    - _Requirements: 1.1, 1.2, 1.4, 4.1, 5.1_
  
  - [ ] 6.2 实现Recommendation Subgraph
    - 创建agents/recommendation_subgraph.py
    - 实现load_profile_node（从Store API加载用户画像）
    - 实现match_products_node（产品匹配逻辑）
    - 实现generate_explanations_node（推荐解释生成）
    - 构建RecommendationState子图
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 18.1_
  
  - [ ] 6.3 实现Compliance Subgraph
    - 创建agents/compliance_subgraph.py
    - 实现check_eligibility_node（投保资格检查）
    - 实现generate_disclosure_node（信息披露生成）
    - 实现log_compliance_node（合规日志记录）
    - 构建ComplianceState子图
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 11.1_
  
  - [ ] 6.4 实现Main Graph（Orchestrator）
    - 创建agents/main_graph.py
    - 定义MainState（包含所有子图数据）
    - 实现profile_node（MainState → ProfileState转换 + 调用子图）
    - 实现recommendation_node（MainState → RecommendationState转换 + 调用子图）
    - 实现compliance_node（MainState → ComplianceState转换 + 调用子图）
    - 构建主图（START → profile → recommendation → compliance → END）
    - 配置checkpointer（PostgresSaver）
    - _Requirements: 4.1, 4.4_
  
  - [ ]* 6.5 编写子图属性测试
    - **Property 5: 用户信息收集完整性**
    - **Validates: Requirements 1.1, 1.2**
    - 验证Profile Subgraph生成的引导问题覆盖所有必要字段
  
  - [ ]* 6.6 编写子图属性测试
    - **Property 7: 缺失字段识别**
    - **Validates: Requirements 1.4**
    - 验证Profile Subgraph能识别所有缺失的必填字段
  
  - [ ]* 6.7 编写子图属性测试
    - **Property 19: 推荐生成非空性**
    - **Validates: Requirements 7.1**
    - 验证Recommendation Subgraph在完整上下文下生成至少一个推荐
  
  - [ ]* 6.8 编写子图属性测试
    - **Property 27: 合规检查执行性**
    - **Validates: Requirements 10.1, 10.2**
    - 验证Compliance Subgraph对所有用户-产品组合都返回合规检查结果
  
  - [ ]* 6.9 编写子图单元测试
    - 测试Profile Subgraph槽位提取正确性
    - 测试Recommendation Subgraph产品匹配逻辑
    - 测试Compliance Subgraph合规检查规则
    - 测试Main Graph状态转换正确性

- [ ] 7. Skills实现
  - [ ] 7.1 实现Insurance Domain Skill
    - 加载保险术语词典（data/insurance_terminology.json）
    - 实现explain_term方法（术语解释）
    - 实现compare_products方法（产品类型对比）
    - 实现explain_claim_process方法（理赔流程说明）
    - _Requirements: 5.3, 8.3_
  
  - [ ] 7.2 实现Risk Assessment Skill
    - 加载风险评估问卷（data/risk_questionnaire.json）
    - 实现assess_risk_preference方法（风险偏好评估）
    - 实现detect_contradictions方法（矛盾检测）
    - 实现generate_clarification_questions方法（澄清问题生成）
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [ ] 7.3 实现Product Matching Skill
    - 加载产品匹配规则（data/product_matching_rules.json）
    - 实现calculate_match_score方法（匹配分数计算）
    - 实现analyze_coverage_gap方法（保障缺口分析）
    - _Requirements: 3.2, 3.3, 7.2_
  
  - [ ] 7.4 实现Compliance Checking Skill
    - 加载合规规则（data/compliance_rules.json）
    - 实现check_eligibility方法（投保资格检查）
    - 实现generate_disclosure方法（信息披露生成）
    - _Requirements: 10.1, 10.2, 11.1_
  
  - [ ]* 7.5 编写Skills单元测试
    - 测试术语解释准确性
    - 测试风险评估分类正确性
    - 测试匹配分数计算逻辑
    - 测试合规检查规则执行

- [ ] 8. 内部工具模块实现
  - [ ] 8.1 实现ProductDatabaseTool
    - 创建tools/product_database.py
    - 实现search_products方法（产品搜索）
    - 实现get_product_details方法（产品详情）
    - 实现check_availability方法（可用性检查）
    - 实现search_by_vector方法（FAISS向量检索）
    - _Requirements: 6.2, 19.1_
  
  - [ ] 8.2 实现UserProfileTool
    - 创建tools/user_profile.py
    - 实现get_user_profile方法（获取用户画像）
    - 实现update_user_profile方法（更新用户画像）
    - 实现get_user_history方法（获取历史会话）
    - _Requirements: 1.3, 12.4_
  
  - [ ] 8.3 实现ComplianceTool
    - 创建tools/compliance.py
    - 实现check_eligibility方法（投保资格检查）
    - 实现generate_disclosure方法（披露要求）
    - 实现log_compliance_check方法（合规日志记录）
    - _Requirements: 10.1, 10.4_
  
  - [ ] 8.4 实现FinancialCalculatorTool
    - 创建tools/financial_calculator.py
    - 实现calculate_affordable_premium方法（可承受保费计算）
    - 实现calculate_coverage_need方法（保障需求计算）
    - _Requirements: 3.3, 7.2_

- [ ] 9. Checkpoint - 确保子图和Skills测试通过
  - 运行所有子图的单元测试和属性测试
  - 验证Skills和Tools集成正常
  - 确认推荐逻辑和合规检查正确
  - 如有问题，询问用户

- [ ] 10. 会话管理器实现
  - [ ] 10.1 实现SessionManager
    - 创建session/session_manager.py
    - 实现create_session方法（创建新会话，配置thread_id）
    - 实现get_session方法（从PostgresSaver恢复会话）
    - 实现switch_session方法（会话切换）
    - 实现process_message方法（调用主图）
    - 实现get_all_messages方法（从PostgresSaver获取消息）
    - 实现close_session方法（可选归档）
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ] 10.2 实现会话隔离机制
    - 实现SessionIsolation（thread_id隔离）
    - 实现ConcurrencyControl（会话锁）
    - 实现BackgroundSessionManager（后台运行支持）
    - _Requirements: 12.1_
  
  - [ ]* 10.3 编写会话管理器单元测试
    - 测试会话隔离（两个会话数据不交叉）
    - 测试会话切换（不中断后台运行）
    - 测试会话恢复（从PostgresSaver）

- [ ] 11. FastAPI接口实现
  - [ ] 11.1 实现核心API路由
    - 创建api/routes.py
    - 实现POST /api/v1/chat/stream（SSE流式响应）
    - 实现GET /api/v1/session/{session_id}（会话恢复）
    - 实现POST /api/v1/session/{session_id}/feedback（用户反馈）
    - 实现GET /api/v1/products/compare（产品对比）
    - _Requirements: API接口_
  
  - [ ] 11.2 实现会话管理API
    - 实现POST /api/v1/sessions/create（创建会话）
    - 实现GET /api/v1/sessions/{session_id}/messages（获取历史消息）
    - 实现GET /api/v1/users/{user_id}/sessions（列出用户会话）
    - 实现POST /api/v1/sessions/switch（切换会话）
    - 实现POST /api/v1/sessions/{session_id}/close（关闭会话）
    - _Requirements: 12.1, 12.2_
  
  - [ ] 11.3 实现SSE流式响应
    - 实现StreamingResponseGenerator
    - 支持多种事件类型（agent_thinking、message_chunk、recommendation、done）
    - 实现错误处理和连接管理
    - _Requirements: API接口_
  
  - [ ]* 11.4 编写API集成测试
    - 测试完整对话流程（创建会话 → 多轮对话 → 推荐 → 关闭）
    - 测试SSE流式响应
    - 测试会话切换和恢复

- [ ] 12. 性能优化实现
  - [ ] 12.1 实现消息数量控制
    - 在节点中控制消息数量（保留最近N条）
    - 配置各Agent的保留轮数
    - _Requirements: 性能优化_
  
  - [ ] 12.2 实现提示词优化
    - 创建精简的提示词模板
    - 实现LayeredPromptManager（分层提示词）
    - 配置各Agent的提示词模板
    - _Requirements: 性能优化_
  
  - [ ] 12.3 实现缓存机制
    - 实现产品特征向量预计算和缓存
    - 实现推荐结果缓存（基于用户画像hash）
    - _Requirements: 性能优化_
  
  - [ ]* 12.4 性能测试
    - 测试Token使用量（目标：6000 tokens/会话）
    - 测试响应时间（目标：P95 < 3s）
    - 测试并发支持（目标：100 QPS）

- [ ] 13. 错误处理和监控
  - [ ] 13.1 实现统一错误处理
    - 创建utils/error_handler.py
    - 实现ErrorHandler（分类处理5类错误）
    - 实现重试机制（指数退避）
    - 实现降级策略（LLM不可用时使用规则引擎）
    - _Requirements: 17.1, 17.2, 17.4_
  
  - [ ] 13.2 实现监控和日志
    - 配置结构化日志（JSON格式）
    - 实现PerformanceMonitor（性能指标收集）
    - 实现QualityMonitor（质量指标评估）
    - 配置告警规则
    - _Requirements: 20.1, 20.2, 20.3_
  
  - [ ]* 13.3 编写错误处理测试
    - 测试各类错误的捕获和处理
    - 测试降级策略触发
    - 测试重试机制

- [ ] 14. Checkpoint - 确保系统集成测试通过
  - 运行端到端集成测试
  - 验证完整对话流程
  - 验证性能指标达标
  - 验证错误处理和降级策略
  - 如有问题，询问用户

- [ ] 15. 数据初始化和种子数据
  - [ ] 15.1 准备保险产品数据
    - 创建data/insurance_products.json（至少50个产品）
    - 包含重疾险、医疗险、意外险、寿险四类
    - 向量化产品并索引到FAISS
    - _Requirements: 6.1_
  
  - [ ] 15.2 准备配置数据
    - 创建data/insurance_terminology.json（术语词典）
    - 创建data/risk_questionnaire.json（风险评估问卷）
    - 创建data/product_matching_rules.json（匹配规则）
    - 创建data/compliance_rules.json（合规规则）
    - _Requirements: Skills配置_

- [ ] 16. 文档编写
  - [ ] 16.1 编写API文档
    - 使用FastAPI自动生成OpenAPI文档
    - 添加API使用示例
    - 文档化SSE事件格式
    - _Requirements: 文档_
  
  - [ ] 16.2 编写部署文档
    - 编写README.md（项目介绍、快速开始）
    - 编写DEPLOYMENT.md（部署指南）
    - 编写docker-compose.yml（容器化部署）
    - 编写环境变量说明
    - _Requirements: 文档_
  
  - [ ] 16.3 编写开发文档
    - 编写CONTRIBUTING.md（开发指南）
    - 文档化架构设计（子图架构、PostgresSaver、Store API）
    - 文档化Skills和MCP扩展方法
    - _Requirements: 文档_

- [ ] 17. 最终测试和验收
  - [ ]* 17.1 运行完整属性测试套件
    - 运行所有属性测试（每个100次迭代）
    - 验证所有属性在随机输入下保持正确
    - 修复发现的边界情况问题
  
  - [ ]* 17.2 运行完整单元测试套件
    - 确保测试覆盖率 > 80%
    - 验证所有核心功能正常
  
  - [ ] 17.3 运行端到端场景测试
    - 测试完整用户旅程（从开始对话到获得推荐）
    - 测试多会话并发场景
    - 测试会话切换和恢复
    - 测试异常场景（网络中断、数据库故障）
  
  - [ ] 17.4 性能和压力测试
    - 使用Locust进行压力测试（目标：100 QPS）
    - 验证响应时间达标（P95 < 3s）
    - 验证Token使用量达标（< 6000 tokens/会话）
    - 验证内存和CPU使用合理

- [ ] 18. Final Checkpoint - 系统验收
  - 确认所有功能需求已实现
  - 确认所有测试通过
  - 确认性能指标达标
  - 确认文档完整
  - 系统可以交付使用

## Notes

- 任务标记`*`的为可选测试任务，可根据时间安排跳过以加快MVP交付
- 每个任务都引用了具体的需求编号，确保可追溯性
- Checkpoint任务用于阶段性验证，确保增量开发质量
- 属性测试使用Hypothesis框架，每个属性测试运行100次迭代
- 单元测试使用pytest框架，目标覆盖率80%以上
- 系统采用Python实现，基于设计文档中的代码示例
- **架构优先级**：
  1. 首先完成子图架构重构（Task 6）
  2. 然后集成PostgresSaver和Store API（Task 4）
  3. 移除HotDataLayer和WarmDataLayer代码
- 子图架构是核心特性，使用LangGraph 1.0.0的StateGraph和子图模式
- PostgresSaver用于会话状态管理（替代HotDataLayer/WarmDataLayer）
- Store API用于跨会话持久化用户画像和关键槽位
- Skills和MCP集成提供系统扩展性，需确保接口清晰
- 会话管理支持多会话隔离和切换，是系统的重要特性
