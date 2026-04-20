# 实现计划: Skills和Tools集成

## 概述

本实现计划涵盖将`InsuranceDomainSkill`和`FinancialCalculatorTool`集成到Profile Subgraph和Recommendation Subgraph。该集成支持在画像收集过程中进行领域知识查询，以及为个性化推荐提供金融计算。

**技术栈**: Python 3.11+, LangGraph 1.0.0, LangChain 1.0.0, Hypothesis (属性测试)

**核心特性**:
- Profile Subgraph集成InsuranceDomainSkill，支持术语、对比和理赔流程查询
- Recommendation Subgraph集成FinancialCalculatorTool，支持保障缺口和可承受性计算
- Recommendation Subgraph集成InsuranceDomainSkill，支持个性化解释生成
- 通过工厂函数参数进行依赖注入
- 优雅降级和回退响应
- 基于模式的问题处理意图检测

**集成模式**: 基于闭包的依赖注入，Skills和Tools传递给工厂函数并在节点函数闭包中捕获。

## 任务

- [x] 1. 创建意图检测模型和模式
  - 创建models/intent.py，包含QuestionType枚举和DetectedIntent模型
  - 定义QUESTION_PATTERNS正则模式，用于术语、对比和理赔问题
  - 定义PRODUCT_TYPE_NAMES映射，将中文产品类型名称映射到英文
  - 在ProfileState中添加question_type和extracted_entities字段
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [-] 2. 在Profile Subgraph中实现意图检测
  - [x] 2.1 在Profile Subgraph中添加detect_intent_node
    - 使用正则匹配实现基于模式的意图检测
    - 从匹配模式中提取实体（术语、产品类型）
    - 根据question_type路由到适当的处理器
    - 用检测到的意图和实体更新ProfileState
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 2.2 编写意图检测属性测试
    - **属性 1: 意图检测路由到正确的处理器**
    - **验证: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
    - 验证问题模式路由到正确的question_type
    - 验证术语、对比和理赔问题的实体提取

- [ ] 3. 将InsuranceDomainSkill集成到Profile Subgraph
  - [x] 3.1 在create_profile_subgraph中添加依赖注入
    - 在create_profile_subgraph函数中添加insurance_skill参数
    - 如果未提供则创建默认InsuranceDomainSkill
    - 通过闭包将skill传递给节点函数
    - _Requirements: 5.1, 5.3, 5.6_

  - [ ] 3.2 为术语问题实现handle_question_node
    - 对术语问题调用InsuranceDomainSkill.explain_term()
    - 格式化响应以便用户显示
    - 保留missing_slots状态以继续画像收集
    - _Requirements: 1.1, 4.1_

  - [ ] 3.3 为对比问题实现handle_question_node
    - 对对比问题调用InsuranceDomainSkill.compare_products()
    - 处理中文和英文产品类型名称
    - 格式化对比结果以便用户显示
    - 处理包含可用产品类型的错误响应
    - _Requirements: 1.2, 4.2_

  - [ ] 3.4 为理赔流程问题实现handle_question_node
    - 对理赔问题调用InsuranceDomainSkill.explain_claim_process()
    - 格式化理赔流程步骤以便用户显示
    - 用回退消息处理无效产品类型
    - _Requirements: 1.3, 4.3_

  - [ ]* 3.5 编写术语解释属性测试
    - **属性 2: 术语解释返回有效响应**
    - **验证: Requirements 1.1, 4.1**
    - 验证explain_term返回非空字符串
    - 验证响应包含已知术语的名称和定义

  - [ ]* 3.6 编写产品对比属性测试
    - **属性 3: 产品对比返回结构化结果**
    - **验证: Requirements 1.2, 4.2**
    - 验证compare_products返回必需字段（product1, product2, comparison）
    - 验证无效产品类型的错误处理

  - [ ]* 3.7 编写理赔流程属性测试
    - **属性 4: 理赔流程返回步骤列表**
    - **验证: Requirements 1.3, 4.3**
    - 验证explain_claim_process对有效产品类型返回非空列表
    - 验证无效产品类型的回退消息

- [ ] 4. 为Profile Subgraph实现错误处理
  - [x] 4.1 在handle_question_node中添加优雅降级
    - 用try-except块包装所有skill调用
    - 当skill失败时返回回退消息
    - 记录错误用于调试，不向用户暴露
    - _Requirements: 4.1, 4.2, 4.3, 4.6_

  - [ ]* 4.2 编写错误处理属性测试
    - **属性 9: 错误处理不传播异常**
    - **验证: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**
    - 验证异常被捕获并返回回退响应
    - 验证错误状态被设置但不传播给用户

- [ ] 5. 更新Profile Subgraph路由以处理问题
  - [x] 5.1 在子图流程中添加问题处理
    - 在extract_slots后添加detect_intent节点
    - 为ask_question意图添加handle_question节点
    - 基于current_intent添加条件路由
    - 确保回答问题后继续画像收集
    - _Requirements: 1.4, 1.5_

  - [ ]* 5.2 编写画像继续属性测试
    - **属性 11: 画像收集在问题后继续**
    - **验证: Requirements 1.4, 1.5**
    - 验证问题处理后保留missing_slots
    - 验证回答后画像收集恢复

- [ ] 6. 检查点 - 确保Profile Subgraph集成测试通过
  - 运行所有Profile Subgraph单元测试和属性测试
  - 验证意图检测正常工作
  - 验证skill集成具有优雅降级
  - 验证问题后画像收集继续
  - 如有问题询问用户

- [ ] 7. 将FinancialCalculatorTool集成到Recommendation Subgraph
  - [ ] 7.1 在create_recommendation_subgraph中添加依赖注入
    - 在create_recommendation_subgraph函数中添加financial_tool参数
    - 如果未提供则创建默认FinancialCalculatorTool
    - 通过闭包将tool传递给节点函数
    - _Requirements: 5.2, 5.3, 5.6_

  - [ ] 7.2 更新match_products_node以使用FinancialCalculatorTool
    - 用tool.calculate_affordable_premium()替换_calculate_affordable_premium_range
    - 调用tool.calculate_coverage_need()获取推荐保额
    - 调用tool.calculate_coverage_gap()进行缺口分析
    - _Requirements: 2.1, 2.2, 2.3, 7.1, 7.2, 7.3, 8.1, 8.2_

  - [ ] 7.3 为tool失败实现回退计算
    - 添加_get_default_coverage_need()回退函数
    - 添加_get_default_coverage_gap()回退函数
    - 用try-except包装tool调用并使用回退逻辑
    - 使用回退计算时记录警告
    - _Requirements: 4.4_

  - [ ]* 7.4 编写保障缺口计算属性测试
    - **属性 5: 保障缺口计算保持不变量**
    - **验证: Requirements 2.1, 2.2, 7.1, 7.2, 7.3, 7.5**
    - 验证所有缺口值为非负数
    - 验证total_gap等于各个缺口之和
    - 验证priority_order包含按缺口排序的产品类型

  - [ ]* 7.5 编写保费可承受性属性测试
    - **属性 6: 保费可承受性在范围内**
    - **验证: Requirements 2.3, 8.1, 8.2**
    - 验证可承受保费在收入的5-15%范围内
    - 验证更大的家庭规模导致更低或相等的保费比例

  - [ ]* 7.6 编写可承受性评估属性测试
    - **属性 7: 可承受性评估返回完整结果**
    - **验证: Requirements 2.4, 8.4, 8.5**
    - 验证结果包含所有必需字段
    - 验证is_affordable与gap符号一致

- [ ] 8. 集成InsuranceDomainSkill用于推荐解释
  - [ ] 8.1 在Recommendation Subgraph中添加insurance_skill
    - 在create_recommendation_subgraph中添加insurance_skill参数
    - 通过闭包将skill传递给generate_explanations_node
    - _Requirements: 3.1, 5.2, 5.6_

  - [ ] 8.2 更新generate_explanations_node以使用InsuranceDomainSkill
    - 为每个推荐调用skill.generate_recommendation_explanation()
    - 传递profile_data、product_data、match_score和coverage_gap
    - 将解释存储在RecommendationResult.explanation中
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 8.3 为解释生成实现LLM回退
    - 添加_generate_llm_explanation()异步函数
    - 使用EXPLANATION_GENERATION_PROMPT进行LLM调用
    - 如果LLM失败则回退到基于模板的解释
    - _Requirements: 3.4, 4.5_

  - [ ]* 8.4 编写解释生成属性测试
    - **属性 10: 解释生成包含必需信息**
    - **验证: Requirements 3.1, 3.2, 3.3, 3.4**
    - 验证解释为非空字符串
    - 验证解释包含产品名称
    - 验证skill失败时回退有效

- [ ] 9. 为Recommendation Subgraph实现错误处理
  - [ ] 9.1 在match_products_node中添加优雅降级
    - 用try-except块包装所有tool调用
    - 当tool失败时使用回退计算
    - 记录错误但不使推荐流程失败
    - _Requirements: 4.4, 4.6_

  - [ ] 9.2 在generate_explanations_node中添加优雅降级
    - 首先尝试基于skill的解释
    - skill失败时回退到基于LLM的解释
    - LLM失败时回退到基于模板的解释
    - _Requirements: 4.5, 4.6_

- [ ] 10. 检查点 - 确保Recommendation Subgraph集成测试通过
  - 运行所有Recommendation Subgraph单元测试和属性测试
  - 验证金融计算正常工作
  - 验证解释生成具有回退
  - 验证tools/skills失败时的优雅降级
  - 如有问题询问用户

- [ ] 11. 编写集成单元测试
  - [ ] 11.1 为Profile Subgraph skill集成编写单元测试
    - 使用mock InsuranceDomainSkill测试handle_question_node
    - 测试意图检测和实体提取
    - 测试错误处理和回退响应
    - 测试使用自定义skill的依赖注入
    - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3, 5.1_

  - [ ] 11.2 为Recommendation Subgraph tool集成编写单元测试
    - 使用mock FinancialCalculatorTool测试match_products_node
    - 使用mock InsuranceDomainSkill测试generate_explanations_node
    - 测试tool失败时的回退计算
    - 测试使用自定义实例的依赖注入
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 4.4, 4.5, 5.2_

- [ ] 12. 编写集成测试
  - [ ] 12.1 为带问题的Profile Subgraph编写端到端测试
    - 测试完整流程：用户提问 → skill响应 → 继续收集
    - 测试连续的多种问题类型
    - 测试问题后的画像完成
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 12.2 为带tools的Recommendation Subgraph编写端到端测试
    - 测试完整流程：画像 → 金融计算 → 推荐 → 解释
    - 测试tools/skills失败时的优雅降级
    - 测试使用自定义实例的依赖注入
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 4.4, 4.5_

- [ ] 13. 更新现有测试以适应新集成
  - [ ] 13.1 更新test_profile_subgraph.py以适应skill集成
    - 为新的detect_intent_node添加测试
    - 为handle_question_node添加测试
    - 更新现有测试以适应新的路由逻辑
    - _Requirements: 测试_

  - [ ] 13.2 更新test_financial_calculator.py以适应新方法
    - 确保现有测试仍然通过
    - 为calculate_coverage_gap方法添加测试
    - 为边界情况和错误条件添加测试
    - _Requirements: 测试_

  - [ ] 13.3 更新test_insurance_domain_skill.py以适应新方法
    - 确保现有测试仍然通过
    - 为generate_recommendation_explanation方法添加测试
    - 为边界情况和错误条件添加测试
    - _Requirements: 测试_

- [ ] 14. 最终检查点 - 确保所有测试通过
  - 运行完整测试套件（单元测试、属性测试、集成测试）
  - 验证所有需求被测试覆盖
  - 验证优雅降级在所有场景下工作
  - 验证依赖注入正常工作
  - 系统准备好部署

## 备注

- 标记为`*`的任务是可选的测试任务，可以跳过以加快MVP交付
- 每个任务引用具体需求以确保可追溯性
- 检查点确保增量验证
- 属性测试使用Hypothesis验证通用正确性属性
- 单元测试验证具体示例和边界情况
- 实现使用Python，遵循设计文档中的代码示例
- **依赖注入模式**: Skills和Tools传递给工厂函数并在节点函数闭包中捕获
- **错误处理策略**: 优雅降级，失败时返回回退响应而不中断对话
- **意图检测**: 使用正则匹配的基于模式的方法进行问题分类
- **测试策略**: 属性测试验证通用属性，单元测试验证具体案例，集成测试验证完整流程
