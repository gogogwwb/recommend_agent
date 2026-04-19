# 保险智能推荐Agent系统

基于LangGraph 1.x多Agent架构的智能对话推荐系统，通过自然语言交互理解C端用户的保险需求，并提供个性化的保险产品推荐。

## 核心特性

- **多Agent协作**：Profile Collection、Recommendation、Compliance三个专门化Agent协同工作
- **子图架构**：LangGraph 1.0.0子图Schema实现Agent隔离，类型安全
- **Store API集成**：PostgresStore管理用户画像，跨会话持久化
- **PostgresSaver**：会话状态持久化和恢复，支持时间旅行调试
- **Skills + Tools集成**：4个Skills + 4个内部工具模块提供可扩展能力
- **会话管理**：支持多会话隔离、切换、后台运行
- **实时流式响应**：FastAPI + SSE提供流式对话体验
- **性能优化**：Token压缩、KV Cache、推荐结果缓存

## 技术栈

- **多Agent框架**：LangGraph 1.0.0 + LangChain 1.0.0
- **State管理**：子图Schema + Store API (PostgresStore) + PostgresSaver (Checkpointer)
- **向量数据库**：FAISS
- **关系数据库**：PostgreSQL
- **后端框架**：FastAPI + SSE
- **Python环境管理**：uv
- **测试框架**：pytest + hypothesis（属性测试）

## 快速开始

### 1. 环境准备

确保已安装：
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- uv（Python包管理器）

### 2. 安装依赖

```bash
# 使用uv安装依赖
uv sync

# 或使用pip
pip install -e .
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件，填入实际配置
# 必须配置：OPENAI_API_KEY, POSTGRES_PASSWORD等
```

### 4. 初始化数据库

```bash
# 运行数据库迁移
alembic upgrade head

# 加载种子数据
python scripts/seed_data.py
```

### 5. 启动服务

```bash
# 启动FastAPI服务
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 测试API

```bash
# 健康检查
curl http://localhost:8000/health

# 开始对话
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "我想了解重疾险", "user_id": "user123"}'
```

## 项目结构

```
insurance-recommendation-agent/
├── agents/              # Agent实现
│   ├── profile_collection_agent.py
│   ├── recommendation_agent.py
│   ├── compliance_agent.py
│   └── orchestrator.py
├── skills/              # Skills模块
│   ├── insurance_domain.py
│   ├── risk_assessment.py
│   ├── product_matching.py
│   └── compliance_checking.py
├── tools/               # 内部工具模块
│   ├── product_database.py
│   ├── user_profile.py
│   ├── compliance.py
│   └── financial_calculator.py
├── api/                 # FastAPI接口
│   ├── routes.py
│   └── main.py
├── models/              # 数据模型
│   ├── subgraph_states.py
│   ├── user.py
│   ├── product.py
│   └── compliance.py
├── utils/               # 工具函数
│   ├── redis_client.py
│   ├── error_handler.py
│   └── performance_monitor.py
├── tests/               # 测试
│   ├── unit/
│   └── property/
├── data/                # 数据文件
│   ├── insurance_products.json
│   ├── insurance_terminology.json
│   └── compliance_rules.json
├── logs/                # 日志文件
├── .env.example         # 环境变量模板
├── logging.yaml         # 日志配置
├── pyproject.toml       # 项目配置
└── README.md
```

## 开发指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行属性测试
pytest tests/property/

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

### 代码格式化

```bash
# 使用black格式化代码
black .

# 使用ruff检查代码
ruff check .
```

### 类型检查

```bash
# 使用mypy进行类型检查
mypy .
```

## 架构说明

系统采用主子架构（Supervisor Pattern），由Orchestrator Agent作为主控节点，协调三个专门化Agent：

1. **Profile Collection Agent**：收集用户画像、评估风险偏好、处理闲聊
2. **Recommendation Agent**：基于RAG检索和匹配算法生成个性化推荐
3. **Compliance Agent**：执行合规检查、生成信息披露

详细架构设计请参考：`.kiro/specs/insurance-recommendation-agent/design.md`

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交Issue或Pull Request。
