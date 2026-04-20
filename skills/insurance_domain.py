"""
保险领域知识技能

负责保险领域知识和术语理解，包括：
- 保险术语解释
- 保险条款解读
- 理赔流程说明
- 保险产品对比
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class InsuranceDomainSkill:
    """保险领域知识技能"""
    
    def __init__(self, terminology_path: Optional[str] = None):
        """初始化保险领域技能
        
        Args:
            terminology_path: 术语词典文件路径，默认为 data/insurance_terminology.json
        """
        if terminology_path is None:
            terminology_path = Path(__file__).parent.parent / "data" / "insurance_terminology.json"
        
        self.terminology_path = Path(terminology_path)
        self.terminology_data = self._load_terminology()
    
    def _load_terminology(self) -> Dict[str, Any]:
        """加载保险术语词典
        
        Returns:
            术语词典数据
        """
        if not self.terminology_path.exists():
            raise FileNotFoundError(f"术语词典文件不存在: {self.terminology_path}")
        
        with open(self.terminology_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def explain_term(self, term: str) -> str:
        """解释保险术语
        
        Args:
            term: 要解释的术语名称
            
        Returns:
            术语解释文本
            
        Raises:
            ValueError: 如果术语不存在
        """
        terminology = self.terminology_data.get("terminology", {})
        
        # 处理空字符串
        if not term or not term.strip():
            return f"未找到术语 '{term}' 的解释。您可以尝试查询其他保险术语，如：重疾险、医疗险、意外险、寿险、等待期、犹豫期等。"
        
        # 查找术语（支持模糊匹配）
        term_data = None
        matched_term = None
        
        # 精确匹配
        if term in terminology:
            term_data = terminology[term]
            matched_term = term
        else:
            # 模糊匹配（包含关系）
            for key in terminology:
                if term in key or key in term:
                    term_data = terminology[key]
                    matched_term = key
                    break
        
        if term_data is None:
            return f"未找到术语 '{term}' 的解释。您可以尝试查询其他保险术语，如：重疾险、医疗险、意外险、寿险、等待期、犹豫期等。"
        
        # 构建解释文本
        explanation_parts = [f"**{matched_term}**\n"]
        explanation_parts.append(f"{term_data['definition']}\n")
        
        # 添加要点
        if "key_points" in term_data:
            explanation_parts.append("\n**要点：**")
            for point in term_data["key_points"]:
                explanation_parts.append(f"- {point}")
        
        # 添加适用人群
        if "suitable_for" in term_data:
            explanation_parts.append("\n**适用人群：**")
            for group in term_data["suitable_for"]:
                explanation_parts.append(f"- {group}")
        
        # 添加常见术语
        if "common_terms" in term_data:
            explanation_parts.append("\n**相关术语：**")
            for term_name, term_def in term_data["common_terms"].items():
                explanation_parts.append(f"- {term_name}：{term_def}")
        
        return "\n".join(explanation_parts)
    
    def compare_products(self, product_type1: str, product_type2: str) -> Dict[str, Any]:
        """对比不同类型的保险产品
        
        Args:
            product_type1: 第一种产品类型（如 critical_illness, medical, accident, life）
            product_type2: 第二种产品类型
            
        Returns:
            对比结果，包含差异点、适用场景等
        """
        product_types = self.terminology_data.get("product_types", {})
        comparison_dimensions = self.terminology_data.get("comparison_dimensions", {})
        
        # 标准化产品类型名称
        type_mapping = {
            "重疾险": "critical_illness",
            "重大疾病保险": "critical_illness",
            "医疗险": "medical",
            "医疗保险": "medical",
            "意外险": "accident",
            "意外伤害保险": "accident",
            "寿险": "life",
            "人寿保险": "life",
            "定期寿险": "life",
            "终身寿险": "life",
        }
        
        product_type1 = type_mapping.get(product_type1, product_type1)
        product_type2 = type_mapping.get(product_type2, product_type2)
        
        # 获取产品信息
        product1_info = product_types.get(product_type1)
        product2_info = product_types.get(product_type2)
        
        if product1_info is None or product2_info is None:
            missing = []
            if product1_info is None:
                missing.append(product_type1)
            if product2_info is None:
                missing.append(product_type2)
            return {
                "error": f"未找到产品类型: {', '.join(missing)}",
                "available_types": list(product_types.keys())
            }
        
        # 查找预定义的对比维度
        comparison_key = f"{product_type1}_vs_{product_type2}"
        reverse_key = f"{product_type2}_vs_{product_type1}"
        
        predefined_comparison = comparison_dimensions.get(comparison_key) or comparison_dimensions.get(reverse_key)
        
        # 构建对比结果
        result = {
            "product1": {
                "type": product_type1,
                "name": product1_info["name"],
                "full_name": product1_info["full_name"],
                "description": product1_info["description"]
            },
            "product2": {
                "type": product_type2,
                "name": product2_info["name"],
                "full_name": product2_info["full_name"],
                "description": product2_info["description"]
            },
            "comparison": []
        }
        
        # 如果有预定义对比维度，使用预定义的
        if predefined_comparison:
            result["comparison"] = predefined_comparison["dimensions"]
            result["recommendation"] = predefined_comparison["recommendation"]
        else:
            # 否则，动态生成对比
            dimensions_to_compare = [
                ("保障范围", "coverage"),
                ("典型保费", "typical_premium_range"),
                ("典型保额", "typical_coverage_range"),
                ("等待期", "waiting_period"),
                ("优势", "advantages"),
                ("劣势", "disadvantages"),
                ("适用场景", "suitable_scenarios")
            ]
            
            for dim_name, dim_key in dimensions_to_compare:
                value1 = product1_info.get(dim_key)
                value2 = product2_info.get(dim_key)
                
                if value1 and value2:
                    if isinstance(value1, list):
                        value1 = "、".join(value1)
                    if isinstance(value2, list):
                        value2 = "、".join(value2)
                    
                    result["comparison"].append({
                        "name": dim_name,
                        product_type1: value1,
                        product_type2: value2
                    })
        
        # 添加综合建议
        if "recommendation" not in result:
            result["recommendation"] = self._generate_comparison_recommendation(
                product_type1, product_type2, product1_info, product2_info
            )
        
        return result
    
    def _generate_comparison_recommendation(
        self, 
        product_type1: str, 
        product_type2: str,
        product1_info: Dict, 
        product2_info: Dict
    ) -> str:
        """生成产品对比建议
        
        Args:
            product_type1: 第一种产品类型
            product_type2: 第二种产品类型
            product1_info: 第一种产品信息
            product2_info: 第二种产品信息
            
        Returns:
            对比建议文本
        """
        # 基于产品类型生成建议
        recommendations = {
            ("critical_illness", "medical"): "重疾险和医疗险互为补充，建议同时配置。重疾险提供一次性资金支持，医疗险报销实际医疗费用。",
            ("accident", "critical_illness"): "意外险作为基础保障，重疾险作为核心保障。意外险保费低廉，建议优先配置；重疾险保障更全面，建议根据预算配置。",
            ("life", "critical_illness"): "寿险和重疾险保障不同风险。寿险保障身故风险，为家人提供经济保障；重疾险保障疾病风险，提供治疗和康复资金。家庭经济支柱建议同时配置。",
            ("accident", "medical"): "意外险和医疗险保障不同场景。意外险仅保障意外事故，医疗险保障疾病和意外医疗费用。建议同时配置以获得全面保障。",
        }
        
        key = (product_type1, product_type2)
        reverse_key = (product_type2, product_type1)
        
        if key in recommendations:
            return recommendations[key]
        elif reverse_key in recommendations:
            return recommendations[reverse_key]
        else:
            return f"建议根据您的实际需求和预算，选择合适的保险产品。如有疑问，可以咨询专业保险顾问。"
    
    def explain_claim_process(self, product_type: str) -> List[str]:
        """解释理赔流程
        
        Args:
            product_type: 产品类型（如 critical_illness, medical, accident, life）
            
        Returns:
            理赔流程步骤列表
        """
        # 标准化产品类型名称
        type_mapping = {
            "重疾险": "critical_illness",
            "重大疾病保险": "critical_illness",
            "医疗险": "medical",
            "医疗保险": "medical",
            "意外险": "accident",
            "意外伤害保险": "accident",
            "寿险": "life",
            "人寿保险": "life",
        }
        
        product_type = type_mapping.get(product_type, product_type)
        
        claim_processes = self.terminology_data.get("claim_processes", {})
        
        if product_type not in claim_processes:
            return [
                f"未找到产品类型 '{product_type}' 的理赔流程。",
                "支持的产品类型：重疾险、医疗险、意外险、寿险。"
            ]
        
        process_data = claim_processes[product_type]
        
        # 构建完整的理赔流程说明
        result = [f"**{process_data['name']}**\n"]
        result.append("**理赔步骤：**")
        result.extend(process_data["steps"])
        
        if "timeline" in process_data:
            result.append(f"\n**理赔时效：** {process_data['timeline']}")
        
        if "notes" in process_data:
            result.append("\n**注意事项：**")
            for note in process_data["notes"]:
                result.append(f"- {note}")
        
        return result
    
    def get_product_type_info(self, product_type: str) -> Optional[Dict[str, Any]]:
        """获取产品类型信息
        
        Args:
            product_type: 产品类型
            
        Returns:
            产品类型信息
        """
        # 标准化产品类型名称
        type_mapping = {
            "重疾险": "critical_illness",
            "重大疾病保险": "critical_illness",
            "医疗险": "medical",
            "医疗保险": "medical",
            "意外险": "accident",
            "意外伤害保险": "accident",
            "寿险": "life",
            "人寿保险": "life",
        }
        
        product_type = type_mapping.get(product_type, product_type)
        
        product_types = self.terminology_data.get("product_types", {})
        return product_types.get(product_type)
    
    def list_available_terms(self) -> List[str]:
        """列出所有可用的术语
        
        Returns:
            术语列表
        """
        terminology = self.terminology_data.get("terminology", {})
        return list(terminology.keys())
    
    def list_available_product_types(self) -> List[str]:
        """列出所有可用的产品类型
        
        Returns:
            产品类型列表
        """
        product_types = self.terminology_data.get("product_types", {})
        return [
            {"type": key, "name": value["name"], "full_name": value["full_name"]}
            for key, value in product_types.items()
        ]
    
    def generate_recommendation_explanation(
        self,
        profile_data: Dict[str, Any],
        product_data: Dict[str, Any],
        match_score: float,
        coverage_gap: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成推荐解释
        
        Args:
            profile_data: 用户画像数据
            product_data: 产品数据
            match_score: 匹配分数
            coverage_gap: 保障缺口数据
            
        Returns:
            推荐解释文本
        """
        product_type = product_data.get("product_type", "")
        product_name = product_data.get("product_name", "")
        
        # 获取产品类型信息
        product_type_info = self.get_product_type_info(product_type)
        
        explanation_parts = [f"**推荐产品：{product_name}**\n"]
        explanation_parts.append(f"匹配度：{match_score:.1f}分\n")
        
        # 基于用户画像生成解释
        age = profile_data.get("age")
        if age:
            explanation_parts.append(f"- 年龄匹配：{age}岁，在投保年龄范围内")
        
        income_range = profile_data.get("income_range")
        if income_range:
            explanation_parts.append(f"- 收入匹配：{income_range}，保费在可承受范围内")
        
        family_size = profile_data.get("family_size")
        has_dependents = profile_data.get("has_dependents")
        if family_size and family_size > 1:
            family_text = f"- 家庭结构：{family_size}口之家"
            if has_dependents:
                family_text += "，有被抚养人需要保障"
            explanation_parts.append(family_text)
        
        # 基于保障缺口生成解释
        if coverage_gap:
            gap_type = None
            if product_type == "critical_illness" and coverage_gap.get("critical_illness_gap", 0) > 0:
                gap_type = "重疾险"
                gap_amount = coverage_gap["critical_illness_gap"]
            elif product_type == "medical" and coverage_gap.get("medical_gap", 0) > 0:
                gap_type = "医疗险"
                gap_amount = coverage_gap["medical_gap"]
            elif product_type == "accident" and coverage_gap.get("accident_gap", 0) > 0:
                gap_type = "意外险"
                gap_amount = coverage_gap["accident_gap"]
            elif product_type == "life" and coverage_gap.get("life_insurance_gap", 0) > 0:
                gap_type = "寿险"
                gap_amount = coverage_gap["life_insurance_gap"]
            
            if gap_type:
                explanation_parts.append(f"- 保障缺口：{gap_type}缺口{gap_amount:.0f}元，该产品可有效弥补缺口")
        
        # 添加产品优势
        if product_type_info and "advantages" in product_type_info:
            explanation_parts.append("\n**产品优势：**")
            for advantage in product_type_info["advantages"][:3]:
                explanation_parts.append(f"- {advantage}")
        
        return "\n".join(explanation_parts)
