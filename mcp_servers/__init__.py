"""
MCP Servers模块 - 已弃用

注意：此模块已弃用，请使用 tools/ 模块替代。
MCP适用于跨进程通信场景，单项目内部调用建议使用内部工具模块。

新模块位置：
- tools/product_database.py (替代 ProductDatabaseMCPServer)
- tools/user_profile.py (替代 UserProfileMCPServer)
- tools/compliance.py (替代 ComplianceRulesMCPServer)
- tools/financial_calculator.py (替代 FinancialCalculatorMCPServer)
"""

import warnings

warnings.warn(
    "mcp_servers模块已弃用，请使用tools模块替代。"
    "单项目内部调用建议使用内部工具模块，避免MCP的进程间通信开销。",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    "ProductDatabaseMCPServer",
    "UserProfileMCPServer",
    "ComplianceRulesMCPServer",
    "FinancialCalculatorMCPServer",
]
