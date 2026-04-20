"""
InsuranceDomainSkill 单元测试
"""
import pytest
from pathlib import Path
from skills.insurance_domain import InsuranceDomainSkill


class TestInsuranceDomainSkill:
    """InsuranceDomainSkill 测试类"""
    
    @pytest.fixture
    def skill(self):
        """创建 InsuranceDomainSkill 实例"""
        return InsuranceDomainSkill()
    
    def test_initialization(self, skill):
        """测试初始化"""
        assert skill.terminology_data is not None
        assert "terminology" in skill.terminology_data
        assert "product_types" in skill.terminology_data
        assert "claim_processes" in skill.terminology_data
    
    def test_initialization_with_custom_path(self, tmp_path):
        """测试使用自定义路径初始化"""
        # 创建临时术语文件
        terminology_data = {
            "terminology": {"测试术语": {"definition": "测试定义"}},
            "product_types": {},
            "claim_processes": {}
        }
        import json
        temp_file = tmp_path / "test_terminology.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(terminology_data, f)
        
        skill = InsuranceDomainSkill(terminology_path=str(temp_file))
        assert skill.terminology_data == terminology_data
    
    def test_initialization_file_not_found(self):
        """测试文件不存在时抛出异常"""
        with pytest.raises(FileNotFoundError):
            InsuranceDomainSkill(terminology_path="nonexistent.json")
    
    def test_explain_term_exact_match(self, skill):
        """测试精确匹配术语解释"""
        result = skill.explain_term("重疾险")
        
        assert "重疾险" in result
        assert "重大疾病保险" in result
        assert "确诊即赔付" in result
    
    def test_explain_term_fuzzy_match(self, skill):
        """测试模糊匹配术语解释"""
        result = skill.explain_term("重疾")
        
        # 应该匹配到"重疾险"
        assert "重疾险" in result or "重疾" in result
    
    def test_explain_term_not_found(self, skill):
        """测试术语不存在时的返回"""
        result = skill.explain_term("不存在的术语")
        
        assert "未找到" in result
        assert "不存在的术语" in result
    
    def test_explain_term_with_common_terms(self, skill):
        """测试包含相关术语的解释"""
        result = skill.explain_term("重疾险")
        
        assert "相关术语" in result or "要点" in result
    
    def test_compare_products_critical_illness_vs_medical(self, skill):
        """测试重疾险与医疗险对比"""
        result = skill.compare_products("critical_illness", "medical")
        
        assert "product1" in result
        assert "product2" in result
        assert "comparison" in result
        assert result["product1"]["type"] == "critical_illness"
        assert result["product2"]["type"] == "medical"
        assert "recommendation" in result
    
    def test_compare_products_with_chinese_names(self, skill):
        """测试使用中文名称对比产品"""
        result = skill.compare_products("重疾险", "医疗险")
        
        assert result["product1"]["type"] == "critical_illness"
        assert result["product2"]["type"] == "medical"
    
    def test_compare_products_invalid_type(self, skill):
        """测试无效产品类型对比"""
        result = skill.compare_products("invalid_type", "medical")
        
        assert "error" in result
        assert "available_types" in result
    
    def test_compare_products_same_type(self, skill):
        """测试相同产品类型对比"""
        result = skill.compare_products("critical_illness", "critical_illness")
        
        assert result["product1"]["type"] == result["product2"]["type"]
    
    def test_explain_claim_process_critical_illness(self, skill):
        """测试重疾险理赔流程"""
        result = skill.explain_claim_process("critical_illness")
        
        assert len(result) > 0
        assert any("重疾险" in step or "理赔" in step for step in result)
    
    def test_explain_claim_process_medical(self, skill):
        """测试医疗险理赔流程"""
        result = skill.explain_claim_process("medical")
        
        assert len(result) > 0
        assert any("医疗" in step or "理赔" in step for step in result)
    
    def test_explain_claim_process_accident(self, skill):
        """测试意外险理赔流程"""
        result = skill.explain_claim_process("accident")
        
        assert len(result) > 0
        assert any("意外" in step or "理赔" in step for step in result)
    
    def test_explain_claim_process_life(self, skill):
        """测试寿险理赔流程"""
        result = skill.explain_claim_process("life")
        
        assert len(result) > 0
        assert any("寿险" in step or "理赔" in step for step in result)
    
    def test_explain_claim_process_with_chinese_name(self, skill):
        """测试使用中文名称获取理赔流程"""
        result = skill.explain_claim_process("重疾险")
        
        assert len(result) > 0
        assert any("重疾险" in step for step in result)
    
    def test_explain_claim_process_invalid_type(self, skill):
        """测试无效产品类型的理赔流程"""
        result = skill.explain_claim_process("invalid_type")
        
        assert len(result) > 0
        assert "未找到" in result[0]
    
    def test_get_product_type_info(self, skill):
        """测试获取产品类型信息"""
        result = skill.get_product_type_info("critical_illness")
        
        assert result is not None
        assert result["name"] == "重疾险"
        assert result["full_name"] == "重大疾病保险"
    
    def test_get_product_type_info_with_chinese_name(self, skill):
        """测试使用中文名称获取产品类型信息"""
        result = skill.get_product_type_info("重疾险")
        
        assert result is not None
        assert result["name"] == "重疾险"
    
    def test_get_product_type_info_invalid(self, skill):
        """测试获取无效产品类型信息"""
        result = skill.get_product_type_info("invalid_type")
        
        assert result is None
    
    def test_list_available_terms(self, skill):
        """测试列出所有可用术语"""
        result = skill.list_available_terms()
        
        assert len(result) > 0
        assert "重疾险" in result
        assert "医疗险" in result
        assert "意外险" in result
        assert "寿险" in result
    
    def test_list_available_product_types(self, skill):
        """测试列出所有可用产品类型"""
        result = skill.list_available_product_types()
        
        assert len(result) > 0
        types = [item["type"] for item in result]
        assert "critical_illness" in types
        assert "medical" in types
        assert "accident" in types
        assert "life" in types
    
    def test_generate_recommendation_explanation(self, skill):
        """测试生成推荐解释"""
        profile_data = {
            "age": 30,
            "income_range": "medium_high",
            "family_size": 3,
            "has_dependents": True
        }
        product_data = {
            "product_type": "critical_illness",
            "product_name": "测试重疾险产品"
        }
        match_score = 85.5
        
        result = skill.generate_recommendation_explanation(
            profile_data, product_data, match_score
        )
        
        assert "测试重疾险产品" in result
        assert "85.5" in result
        assert "30岁" in result
    
    def test_generate_recommendation_explanation_with_coverage_gap(self, skill):
        """测试带保障缺口的推荐解释"""
        profile_data = {
            "age": 35,
            "income_range": "medium",
            "family_size": 4
        }
        product_data = {
            "product_type": "critical_illness",
            "product_name": "测试重疾险产品"
        }
        match_score = 90.0
        coverage_gap = {
            "critical_illness_gap": 300000
        }
        
        result = skill.generate_recommendation_explanation(
            profile_data, product_data, match_score, coverage_gap
        )
        
        assert "保障缺口" in result
        assert "300000" in result


class TestInsuranceDomainSkillEdgeCases:
    """InsuranceDomainSkill 边界情况测试"""
    
    @pytest.fixture
    def skill(self):
        """创建 InsuranceDomainSkill 实例"""
        return InsuranceDomainSkill()
    
    def test_explain_term_empty_string(self, skill):
        """测试空字符串术语"""
        result = skill.explain_term("")
        
        # 应该返回未找到的提示
        assert "未找到" in result
    
    def test_compare_products_reverse_order(self, skill):
        """测试反向顺序对比产品"""
        result1 = skill.compare_products("critical_illness", "medical")
        result2 = skill.compare_products("medical", "critical_illness")
        
        # 两种顺序都应该返回有效的对比结果
        assert "comparison" in result1
        assert "comparison" in result2
    
    def test_generate_recommendation_explanation_minimal_data(self, skill):
        """测试最小数据的推荐解释"""
        profile_data = {}
        product_data = {
            "product_type": "critical_illness",
            "product_name": "测试产品"
        }
        match_score = 50.0
        
        result = skill.generate_recommendation_explanation(
            profile_data, product_data, match_score
        )
        
        assert "测试产品" in result
        assert "50.0" in result
    
    def test_all_product_types_have_claim_process(self, skill):
        """测试所有产品类型都有理赔流程"""
        product_types = skill.list_available_product_types()
        
        for product_type in product_types:
            claim_process = skill.explain_claim_process(product_type["type"])
            assert len(claim_process) > 0, f"{product_type['type']} 缺少理赔流程"
    
    def test_all_product_types_have_info(self, skill):
        """测试所有产品类型都有完整信息"""
        product_types = skill.list_available_product_types()
        
        for product_type in product_types:
            info = skill.get_product_type_info(product_type["type"])
            assert info is not None, f"{product_type['type']} 缺少产品信息"
            assert "name" in info
            assert "full_name" in info
            assert "description" in info
