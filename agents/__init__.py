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

__all__ = [
    # Profile Subgraph
    "create_profile_subgraph",
    "run_profile_subgraph",
    "REQUIRED_SLOTS",
    "OPTIONAL_SLOTS",
    "INTENT_TYPES",
    # Legacy exports (to be updated as other subgraphs are implemented)
    "ProfileCollectionAgent",
    "RecommendationAgent",
    "ComplianceAgent",
    "OrchestratorAgent",
]
