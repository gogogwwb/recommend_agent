# 需求文档

## 引言

本文档定义了将Skills和Tools集成到保险推荐系统Agent子图的需求。系统已有`InsuranceDomainSkill`和`FinancialCalculatorTool`的实现，需要将它们集成到Profile Subgraph和Recommendation Subgraph中，以提供领域专业知识和金融计算能力。

## 术语表

- **InsuranceDomainSkill**: 保险领域知识技能模块，提供保险术语解释、产品对比、理赔流程说明和推荐解释生成功能。
- **FinancialCalculatorTool**: 金融计算工具模块，提供可承受保费计算、保障需求计算、保费收入比计算和保障缺口分析功能。
- **Profile Subgraph**: 负责通过自然对话收集用户画像信息的LangGraph子图。
- **Recommendation Subgraph**: 负责生成个性化保险产品推荐的LangGraph子图。
- **Skill**: 可复用的领域知识模块，提供专业能力（如保险术语、产品知识）。
- **Tool**: 可复用的计算模块，提供特定计算或操作（如金融计算）。
- **Dependency Injection**: 一种设计模式，依赖项（Skills/Tools）通过参数传递给组件，而不是在组件内部创建。

## 需求

### 需求 1: Profile Subgraph集成InsuranceDomainSkill

**用户故事:** 作为用户，我希望在画像收集过程中询问保险术语和概念，以便在做决策前更好地理解保险术语。

#### 验收标准

1. WHEN 用户在画像收集过程中询问保险术语，THE Profile_Subgraph SHALL 使用InsuranceDomainSkill.explain_term()提供解释
2. WHEN 用户在画像收集过程中要求对比保险产品类型，THE Profile_Subgraph SHALL 使用InsuranceDomainSkill.compare_products()提供对比结果
3. WHEN 用户在画像收集过程中询问产品类型的理赔流程，THE Profile_Subgraph SHALL 使用InsuranceDomainSkill.explain_claim_process()解释流程
4. THE Profile_Subgraph SHALL 检测用户意图是提问还是提供画像信息
5. THE Profile_Subgraph SHALL 在回答用户问题后继续画像收集

### 需求 2: Recommendation Subgraph集成FinancialCalculatorTool

**用户故事:** 作为用户，我希望推荐基于准确的金融计算，以便推荐的产品符合我的财务状况和保障需求。

#### 验收标准

1. WHEN 分析保障缺口，THE Recommendation_Subgraph SHALL 使用FinancialCalculatorTool.calculate_coverage_need()确定推荐保额
2. WHEN 分析保障缺口，THE Recommendation_Subgraph SHALL 使用FinancialCalculatorTool.calculate_coverage_gap()计算推荐保额与已有保障之间的缺口
3. WHEN 确定可承受保费范围，THE Recommendation_Subgraph SHALL 使用FinancialCalculatorTool.calculate_affordable_premium()替代硬编码逻辑
4. WHEN 评估保费可承受性，THE Recommendation_Subgraph SHALL 使用FinancialCalculatorTool.evaluate_premium_affordability()评估保费是否在预算内
5. THE Recommendation_Subgraph SHALL 将UserProfile和已有保障数据传递给FinancialCalculatorTool方法

### 需求 3: Recommendation Subgraph集成InsuranceDomainSkill生成解释

**用户故事:** 作为用户，我希望获得清晰的产品推荐理由，以便理解推荐原因并做出明智决策。

#### 验收标准

1. WHEN 生成推荐解释，THE Recommendation_Subgraph SHALL 使用InsuranceDomainSkill.generate_recommendation_explanation()创建个性化解释
2. THE Recommendation_Subgraph SHALL 将画像数据、产品数据、匹配分数和保障缺口传递给解释生成方法
3. WHEN InsuranceDomainSkill生成解释，THE Recommendation_Subgraph SHALL 将解释存储在RecommendationResult.explanation字段
4. WHEN InsuranceDomainSkill生成解释失败，THE Recommendation_Subgraph SHALL 回退到基于LLM的解释生成

### 需求 4: Skills或Tools失败时的错误处理

**用户故事:** 作为用户，我希望即使领域技能或工具遇到错误，系统仍能继续运行，以便我仍能获得帮助。

#### 验收标准

1. WHEN InsuranceDomainSkill.explain_term()失败，THE Profile_Subgraph SHALL 返回建议用户尝试其他术语或咨询顾问的回退消息
2. WHEN InsuranceDomainSkill.compare_products()失败，THE Profile_Subgraph SHALL 返回包含可用产品类型的错误消息
3. WHEN InsuranceDomainSkill.explain_claim_process()失败，THE Profile_Subgraph SHALL 返回包含通用理赔流程信息的回退消息
4. WHEN FinancialCalculatorTool方法失败，THE Recommendation_Subgraph SHALL 记录错误并使用回退计算逻辑
5. WHEN InsuranceDomainSkill.generate_recommendation_explanation()失败，THE Recommendation_Subgraph SHALL 使用基于LLM的回退解释生成
6. THE Subgraphs SHALL 捕获Skills和Tools的异常，不将错误传播到用户界面

### 需求 5: Skills和Tools的配置和依赖注入

**用户故事:** 作为开发者，我希望Skills和Tools通过配置注入到子图中，以便我可以轻松测试、模拟和替换实现。

#### 验收标准

1. THE Profile_Subgraph SHALL 通过依赖注入接受可选的InsuranceDomainSkill实例
2. THE Recommendation_Subgraph SHALL 通过依赖注入接受可选的FinancialCalculatorTool和InsuranceDomainSkill实例
3. WHEN 未提供Skill或Tool实例，THE Subgraphs SHALL 创建标准配置的默认实例
4. THE 子图工厂函数（create_profile_subgraph, create_recommendation_subgraph）SHALL 接受Skills和Tools作为可选参数
5. THE Skills和Tools SHALL 存储在子图状态中或通过闭包传递给节点函数
6. WHEN 注入Skills或Tools，THE Subgraphs SHALL 使用注入的实例而不是创建新实例

### 需求 6: Profile Subgraph中问题处理的意图检测

**用户故事:** 作为用户，我希望系统能理解我是在提问还是提供信息，以便它能做出适当响应。

#### 验收标准

1. WHEN 用户消息包含问题模式（如"什么是"、"怎么理赔"、"有什么区别"），THE Profile_Subgraph SHALL 将意图分类为"ask_question"
2. WHEN 意图为"ask_question"且问题与保险术语相关，THE Profile_Subgraph SHALL 路由到InsuranceDomainSkill.explain_term()
3. WHEN 意图为"ask_question"且问题与产品对比相关，THE Profile_Subgraph SHALL 路由到InsuranceDomainSkill.compare_products()
4. WHEN 意图为"ask_question"且问题与理赔流程相关，THE Profile_Subgraph SHALL 路由到InsuranceDomainSkill.explain_claim_process()
5. WHEN 意图为"ask_question"但主题与保险无关，THE Profile_Subgraph SHALL 返回礼貌的引导消息

### 需求 7: 使用FinancialCalculatorTool进行保障缺口分析

**用户故事:** 作为用户，我希望基于我的画像获得准确的保障缺口分析，以便我知道我缺少哪些保障。

#### 验收标准

1. WHEN Recommendation_Subgraph分析保障缺口，THE Subgraph SHALL 调用FinancialCalculatorTool.calculate_coverage_need()并传入UserProfile以获取推荐保额
2. WHEN Recommendation_Subgraph分析保障缺口，THE Subgraph SHALL 调用FinancialCalculatorTool.calculate_coverage_gap()并传入UserProfile和已有保障以获取缺口金额
3. THE FinancialCalculatorTool.calculate_coverage_gap() SHALL 返回包含critical_illness_gap、medical_gap、accident_gap、life_gap、total_gap和priority_order的字典
4. THE Recommendation_Subgraph SHALL 使用calculate_coverage_gap()返回的priority_order来确定产品推荐优先级
5. WHEN 用户没有已有保障，THE FinancialCalculatorTool SHALL 将所有保障金额视为零

### 需求 8: 使用FinancialCalculatorTool进行保费可承受性计算

**用户故事:** 作为用户，我希望推荐符合我的预算，以便我可以承担保费而不会造成经济压力。

#### 验收标准

1. WHEN 计算可承受保费范围，THE Recommendation_Subgraph SHALL 调用FinancialCalculatorTool.calculate_affordable_premium()并传入年收入和家庭人数
2. THE FinancialCalculatorTool.calculate_affordable_premium() SHALL 返回基于年收入5-15%并根据家庭人数调整的保费金额
3. WHEN 筛选产品，THE Recommendation_Subgraph SHALL 使用可承受保费范围调整收入匹配分数
4. WHEN 评估特定产品的可承受性，THE Recommendation_Subgraph SHALL 调用FinancialCalculatorTool.evaluate_premium_affordability()并传入总保费、年收入和家庭人数
5. THE evaluate_premium_affordability() SHALL 返回is_affordable、ratio、affordable_premium、gap和recommendation字段
