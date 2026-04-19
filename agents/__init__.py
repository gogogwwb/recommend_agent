"""
Agents模块 - 包含所有Agent实现

本模块包含基于LangGraph 1.0.0子图架构的Agent实现：
- Profile Subgraph: 用户画像收集子图
- Recommendation Subgraph: 产品推荐子图
- Compliance Subgraph: 合规检查子图
- Main Graph: 主图（Orchestrator）
"""

from agents.profile_subgraph import (
    create_profile_subgraph,
    run_profile_subgraph,
    REQUIRED_SLOTS,
    OPTIONAL_SLOTS,
    INTENT_TYPES,
)

from agents.recommendation_subgraph import (
    create_recommendation_subgraph,
    run_recommendation_subgraph,
    MIN_RECOMMENDATIONS,
    MAX_RECOMMENDATIONS,
    PRODUCT_TYPES,
)

from agents.compliance_subgraph import (
    create_compliance_subgraph,
    run_compliance_subgraph,
    COMPLIANCE_CHECK_TYPES,
    HIGH_RISK_OCCUPATIONS,
)

from agents.main_graph import (
    create_main_graph,
    create_main_graph_with_checkpointer,
    run_main_graph,
    process_user_message,
    AGENT_ORDER,
    MAX_RETRY_ATTEMPTS,
)

__all__ = [
    # Profile Subgraph
    "create_profile_subgraph",
    "run_profile_subgraph",
    "REQUIRED_SLOTS",
    "OPTIONAL_SLOTS",
    "INTENT_TYPES",
    
    # Recommendation Subgraph
    "create_recommendation_subgraph",
    "run_recommendation_subgraph",
    "MIN_RECOMMENDATIONS",
    "MAX_RECOMMENDATIONS",
    "PRODUCT_TYPES",
    
    # Compliance Subgraph
    "create_compliance_subgraph",
    "run_compliance_subgraph",
    "COMPLIANCE_CHECK_TYPES",
    "HIGH_RISK_OCCUPATIONS",
    
    # Main Graph (Orchestrator)
    "create_main_graph",
    "create_main_graph_with_checkpointer",
    "run_main_graph",
    "process_user_message",
    "AGENT_ORDER",
    "MAX_RETRY_ATTEMPTS",
]
