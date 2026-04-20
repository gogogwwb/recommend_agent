"""
Skills模块 - 可复用的能力模块
"""

from skills.insurance_domain import InsuranceDomainSkill

__all__ = [
    "InsuranceDomainSkill",
    "RiskAssessmentSkill",
    "ProductMatchingSkill",
    "ComplianceCheckingSkill",
]
